from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

from django.test import TestCase
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.competition.models import Match
from backend.apps.competition.runtime import configure_match_run, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.problems import compilers
from backend.apps.problems.bundle import parse_problem_bundle
from backend.apps.problems.catalog import DjangoProblemCatalog
from backend.apps.problems.compilers import COMPILERS
from backend.apps.problems.storage import store_bundle
from backend.apps.problems.tests.bundle_fixtures import PROBLEM_ID, make_bundle_archive
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant

START = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
VERIFIED = {"cpp20": replace(COMPILERS["cpp20"], verified=True)}


class MatchProblemWorkspaceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.admin = User.objects.create_user(
            email="workspace-admin@example.test", display_name="Admin",
            password="test-password-123456", role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"workspace-player-{index}@example.test", display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(4)
        ]
        tournament = Tournament.objects.create(
            title="Workspace API", starts_at=START, ends_at=START + timedelta(hours=1),
            participant_limit=4, created_by=self.admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(tournament.pk, player.pk, seed=index)
        self.match = next(item for item in generate_bracket(tournament.pk) if item.kind == Match.Kind.PLAYED)
        store_bundle(parse_problem_bundle(make_bundle_archive()), compiler_registry=VERIFIED)
        self.problem_id = PROBLEM_ID
        self.run = configure_match_run(
            self.match.pk, problem_ids=[self.problem_id], allowed_duration_ms=600_000,
            start_mode="manual", scoring_rule=None,
            catalog=DjangoProblemCatalog(compiler_registry=VERIFIED),
        )
        self.frozen = [User.objects.get(pk=UUID(value)) for value in self.run.participant_user_ids]
        self.outsider = next(player for player in self.players if player.pk not in {u.pk for u in self.frozen})
        self.url = f"/api/v1/matches/{self.match.pk}/problems/{self.problem_id}"

    def start(self):
        start_match_run(self.run.pk, now=START)

    def test_anonymous_is_refused_and_outsider_cannot_probe_the_match(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_condition_stays_hidden_until_the_server_started_the_run(self):
        self.client.force_login(self.frozen[0])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "condition_not_available")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_started_run_returns_the_pinned_public_statement_without_private_fields(self):
        self.start()
        self.client.force_login(self.frozen[0])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["problemId"], str(self.problem_id))
        self.assertEqual(body["version"], "synthetic-v1")
        self.assertTrue(body["conditionAvailable"])
        self.assertEqual(body["examples"], [{"input": "2 3\n", "output": "5\n"}])
        self.assertEqual(body["timeLimitMs"], 2000)
        self.assertFalse({"checksum", "tests", "privateArtifacts", "referenceSolution"} & set(body))
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_admin_may_read_the_statement_and_an_unknown_problem_is_not_found(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        other = f"/api/v1/matches/{self.match.pk}/problems/00000000-0000-4000-8000-0000000000ff"
        self.assertEqual(self.client.get(other).status_code, 404)

    def test_languages_offer_only_verified_compilers_with_templates(self):
        self.start()
        self.client.force_login(self.frozen[1])

        with patch.object(compilers, "COMPILERS", VERIFIED):
            verified = self.client.get(f"{self.url}/languages")
        unverified = self.client.get(f"{self.url}/languages")

        self.assertEqual(verified.status_code, 200)
        self.assertEqual([item["id"] for item in verified.json()], ["cpp20"])
        self.assertEqual(set(verified.json()[0]), {"id", "name", "template"})
        self.assertEqual(unverified.status_code, 200)
        self.assertEqual(unverified.json(), [])

    def test_unconfigured_match_is_not_found(self):
        self.match.__class__.objects.filter(pk=self.match.pk).update(current_run=None)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 404)

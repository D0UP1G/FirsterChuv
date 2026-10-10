import json
from unittest.mock import patch
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.common.contracts import AttemptReceipt, ResultReceipt
from backend.apps.competition.domain.scoring import Verdict
from backend.apps.competition.ledger_persistence import apply_result, register_accepted
from backend.apps.competition.models import Match
from backend.apps.competition.runtime import configure_match_run, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.events.models import MatchEvent, MatchSnapshot
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.share_links import create_share_link, revoke_share_link
from backend.apps.common.throttles import RemoteAddressScopedRateThrottle
from backend.apps.tournaments.services import assign_participant


class PublicSnapshotCatalog:
    def __init__(self, problem_id):
        self.problem_id = problem_id

    def describe_ready(self, problem_ids):
        return tuple(
            SimpleNamespace(
                problem_id=problem_id,
                version="v1",
                label="A",
                time_limit_ms=1000,
                memory_limit_bytes=64_000_000,
                languages=(SimpleNamespace(id="python3"),),
            )
            for problem_id in problem_ids
        )

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(problem_id=problem_id, version=version, checksum="a" * 64)


class PublicMatchSnapshotAPITests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.admin = User.objects.create_user(
            email="public-snapshot-admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"public-snapshot-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        self.tournament = Tournament.objects.create(
            title="Public snapshot",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            participant_limit=2,
            created_by=self.admin,
            visibility=Tournament.Visibility.PUBLIC,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(self.tournament.pk, player.pk, seed=index)
        self.match = next(
            item
            for item in generate_bracket(self.tournament.pk)
            if item.kind == Match.Kind.PLAYED
        )
        self.problem_id = uuid4()
        self.run = configure_match_run(
            self.match.pk,
            problem_ids=[self.problem_id],
            allowed_duration_ms=600_000,
            start_mode="manual",
            scoring_rule=None,
            catalog=PublicSnapshotCatalog(self.problem_id),
        )
        self.started_at = timezone.now()
        start_match_run(self.run.pk, now=self.started_at)
        self.run.refresh_from_db()
        self.match.refresh_from_db()
        self.client = APIClient(enforce_csrf_checks=True)

    def add_result(self):
        received_at = self.started_at + timedelta(seconds=20)
        accepted = register_accepted(
            AttemptReceipt(
                submission_id=uuid4(),
                run_id=self.run.pk,
                user_id=self.players[0].pk,
                problem_id=self.problem_id,
                received_at=received_at,
                elapsed_ms=20_000,
                scoring_version=self.run.scoring_version,
            )
        )
        self.assertTrue(
            apply_result(
                ResultReceipt(
                    submission_id=accepted.pk,
                    run_id=accepted.run_id,
                    user_id=accepted.user_id,
                    problem_id=accepted.problem_id,
                    received_at=accepted.received_at,
                    elapsed_ms=accepted.elapsed_ms,
                    scoring_version=accepted.scoring_version,
                    verdict=Verdict.WA,
                )
            )
        )

    def test_anonymous_public_snapshot_uses_atomic_score_event_projection(self):
        self.add_result()

        response = self.client.get(f"/api/v1/public/matches/{self.match.pk}")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        payload = response.json()
        self.assertEqual(
            set(payload),
            {
                "matchId",
                "runId",
                "status",
                "serverNow",
                "elapsedMs",
                "remainingMs",
                "allowedDurationMs",
                "leaderUserId",
                "winnerUserId",
                "lastEventId",
                "scoringRule",
                "players",
            },
        )
        self.assertEqual(payload["matchId"], str(self.match.pk))
        self.assertEqual(payload["runId"], str(self.run.pk))
        self.assertEqual(payload["lastEventId"], MatchEvent.objects.get(match_id=self.match.pk).pk)
        self.assertEqual(payload["players"][0]["tasks"][0]["attempts"], 1)
        self.assertEqual(payload["players"][0]["tasks"][0]["lastVerdict"], "WA")
        self.assertEqual(
            MatchSnapshot.objects.get(match_id=self.match.pk).last_event_id,
            payload["lastEventId"],
        )
        schema_document = json.loads(
            (Path(__file__).resolve().parents[3] / "contracts/mvp-v1/schemas.json").read_text()
        )
        schema = {
            "$schema": schema_document["$schema"],
            "$defs": schema_document["$defs"],
            "$ref": "#/$defs/public-match",
        }
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
        serialized = str(payload).lower()
        for private_field in ("source", "email", "checksum", "diagnostic", "infrastructurefailures"):
            self.assertNotIn(private_field, serialized)
        self.assertNotIn("@example.test", serialized)

    def test_unlisted_match_is_hidden_from_anonymous_public_endpoint(self):
        self.tournament.visibility = Tournament.Visibility.UNLISTED
        self.tournament.save(update_fields=("visibility", "updated_at"))

        response = self.client.get(f"/api/v1/public/matches/{self.match.pk}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_unlisted_read_requires_scoped_unexpired_share_header(self):
        self.tournament.visibility = Tournament.Visibility.UNLISTED
        self.tournament.save(update_fields=("visibility", "updated_at"))
        _link, token = create_share_link(
            self.tournament,
            self.admin,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        path = f"/api/v1/public/matches/{self.match.pk}"

        query_token = self.client.get(path, {"shareToken": token})
        valid = self.client.get(path, HTTP_X_TOURNAMENT_SHARE_TOKEN=token)
        mutation = self.client.post(
            path,
            {},
            format="json",
            HTTP_X_TOURNAMENT_SHARE_TOKEN=token,
        )
        other_tournament = Tournament.objects.create(
            title="Other unlisted tournament",
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1),
            participant_limit=2,
            visibility=Tournament.Visibility.UNLISTED,
            created_by=self.admin,
        )
        other_match = Match.objects.create(
            tournament=other_tournament,
            round_index=1,
            position=999,
            kind=Match.Kind.PLAYED,
        )
        wrong_object = self.client.get(
            f"/api/v1/public/matches/{other_match.pk}",
            HTTP_X_TOURNAMENT_SHARE_TOKEN=token,
        )

        self.assertEqual(query_token.status_code, 404)
        self.assertEqual(valid.status_code, 200, valid.content)
        self.assertEqual(valid["Cache-Control"], "no-store")
        self.assertEqual(valid["Referrer-Policy"], "no-referrer")
        self.assertEqual(mutation.status_code, 405)
        self.assertEqual(wrong_object.status_code, 404)

        expired_link, expired_token = create_share_link(
            self.tournament,
            self.admin,
            expires_at=timezone.now() + timedelta(seconds=1),
        )
        expired_link.expires_at = timezone.now() - timedelta(seconds=1)
        expired_link.save(update_fields=("expires_at",))
        expired = self.client.get(
            path, HTTP_X_TOURNAMENT_SHARE_TOKEN=expired_token
        )
        self.assertEqual(expired.status_code, 404)
        self.assertEqual(expired["Referrer-Policy"], "no-referrer")

        revoke_share_link(self.tournament.pk, _link.pk)
        revoked = self.client.get(path, HTTP_X_TOURNAMENT_SHARE_TOKEN=token)
        self.assertEqual(revoked.status_code, 404)

    def test_public_rate_limit_ignores_spoofed_forwarded_for(self):
        cache.clear()
        path = f"/api/v1/public/matches/{self.match.pk}"
        with patch.dict(
            RemoteAddressScopedRateThrottle.extra_rates,
            {"public_snapshot": "1/minute"},
        ):
            first = self.client.get(
                path,
                REMOTE_ADDR="198.51.100.10",
                HTTP_X_FORWARDED_FOR="203.0.113.1",
            )
            second = self.client.get(
                path,
                REMOTE_ADDR="198.51.100.10",
                HTTP_X_FORWARDED_FOR="203.0.113.2",
            )

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 429, second.content)

    def test_public_match_without_a_configured_run_has_no_partial_dto(self):
        self.match.current_run = None
        self.match.save(update_fields=("current_run", "updated_at"))

        response = self.client.get(f"/api/v1/public/matches/{self.match.pk}")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "public_snapshot_not_ready")

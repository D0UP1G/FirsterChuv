from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.competition.models import Match, MatchRun
from backend.apps.competition.runtime import configure_match_run, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant


class Catalog:
    def __init__(self, problem_id):
        self.problem_id = problem_id

    def describe_ready(self, problem_ids):
        return (SimpleNamespace(
            problem_id=self.problem_id,
            version="v1",
            label="A",
            time_limit_ms=1000,
            memory_limit_bytes=64_000_000,
            languages=(SimpleNamespace(id="python3"),),
        ),)

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(problem_id=problem_id, version=version, checksum="c" * 64)


class MatchAdminApiTests(TestCase):
    def setUp(self):
        self.start = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.admin = User.objects.create_user(
            email="admin-api@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"admin-api-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        tournament = Tournament.objects.create(
            title="Admin actions API",
            starts_at=self.start,
            ends_at=self.start + timedelta(hours=1),
            participant_limit=2,
            created_by=self.admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(tournament.pk, player.pk, seed=index)
        self.match = next(
            match for match in generate_bracket(tournament.pk)
            if match.kind == Match.Kind.PLAYED
        )
        problem_id = uuid4()
        self.run = configure_match_run(
            self.match.pk,
            problem_ids=[problem_id],
            allowed_duration_ms=600_000,
            start_mode="manual",
            scoring_rule=None,
            catalog=Catalog(problem_id),
        )
        start_match_run(self.run.pk, now=self.start)
        self.client = APIClient(enforce_csrf_checks=True)

    def login_with_csrf(self, user):
        self.client.force_login(user)
        response = self.client.get("/api/v1/auth/csrf")
        self.client.credentials(HTTP_X_CSRFTOKEN=response.json()["csrfToken"])

    def post(self, action, *, key, payload):
        return self.client.post(
            f"/api/v1/matches/{self.match.pk}/{action}",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_pause_resume_extend_rematch_and_technical_result_routes(self):
        self.login_with_csrf(self.admin)
        first = self.post("pause", key="api-pause-1", payload={"reason": "Safety"})
        replay = self.post("pause", key="api-pause-1", payload={"reason": "Safety"})
        self.assertEqual(first.status_code, 200, first.json())
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(first.json()["status"], MatchRun.Status.PAUSED)
        changed_intent = self.post("pause", key="api-pause-1", payload={"reason": "Changed"})
        self.assertEqual(changed_intent.status_code, 409)

        resumed = self.post("resume", key="api-resume-1", payload={})
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["status"], MatchRun.Status.RUNNING)
        extended = self.post(
            "extend",
            key="api-extend-1",
            payload={"seconds": 30, "reason": "Short interruption"},
        )
        self.assertEqual(extended.status_code, 200)
        self.assertEqual(extended.json()["allowedDurationMs"], 630_000)

        rematched = self.post(
            "rematches",
            key="api-rematch-1",
            payload={"reason": "Agreed replay"},
        )
        self.assertEqual(rematched.status_code, 200)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, MatchRun.Status.SUPERSEDED)
        self.assertEqual(rematched.json()["status"], MatchRun.Status.READY)

        technical = self.post(
            "technical-result",
            key="api-technical-1",
            payload={"winnerUserId": str(self.players[1].pk), "reason": "Withdrawal"},
        )
        self.assertEqual(technical.status_code, 200)
        self.assertEqual(technical.json()["status"], MatchRun.Status.FINISHED)
        self.assertEqual(technical.json()["winnerUserId"], str(self.players[1].pk))

    def test_replacement_route_uses_strict_request_and_updates_run(self):
        self.login_with_csrf(self.admin)
        replacement = User.objects.create_user(
            email="admin-api-replacement@example.test",
            display_name="Replacement",
            password="test-password-123456",
        )
        old_user_id = self.match.slots.get(slot_index=0).participant.user_id

        response = self.post(
            "replacements",
            key="api-replace-1",
            payload={
                "oldUserId": str(old_user_id),
                "newUserId": str(replacement.pk),
                "reason": "Participant unavailable",
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["action"], "replace_participant")
        self.assertEqual(response.json()["status"], MatchRun.Status.READY)
        self.assertEqual(response.json()["replacementUserId"], str(replacement.pk))
        self.match.refresh_from_db()
        self.assertEqual(
            self.match.current_run.participant_user_ids[0],
            str(replacement.pk),
        )

    def test_admin_routes_enforce_role_csrf_and_idempotency_and_reject_extra_fields(self):
        self.login_with_csrf(self.players[0])
        participant_response = self.post(
            "pause",
            key="api-player-1",
            payload={"reason": "No access"},
        )
        self.assertEqual(participant_response.status_code, 403)

        no_csrf = APIClient(enforce_csrf_checks=True)
        no_csrf.force_login(self.admin)
        missing_csrf = no_csrf.post(
            f"/api/v1/matches/{self.match.pk}/pause",
            {"reason": "No token"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-no-csrf",
        )
        self.assertEqual(missing_csrf.status_code, 403)

        self.login_with_csrf(self.admin)
        extra_field = self.post(
            "pause",
            key="api-extra-1",
            payload={"reason": "Bad shape", "actorId": str(self.admin.pk)},
        )
        self.assertEqual(extra_field.status_code, 400)
        missing_key = self.client.post(
            f"/api/v1/matches/{self.match.pk}/pause",
            {"reason": "Missing idempotency"},
            format="json",
        )
        self.assertEqual(missing_key.status_code, 400)

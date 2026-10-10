import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from django.db import OperationalError
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.common.contracts import (
    AttemptReceipt,
    InfrastructureFailureReceipt,
    ResultReceipt,
)
from backend.apps.competition.domain.scoring import Verdict
from backend.apps.competition.ledger_persistence import (
    apply_result,
    record_infrastructure_failure,
    register_accepted,
)
from backend.apps.competition.models import (
    Match,
    MatchRun,
    MatchRunReady,
)
from backend.apps.competition.services import generate_bracket
from backend.apps.submissions.models import Submission
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant


class ReadyTestCatalog:
    def describe_ready(self, problem_ids):
        return tuple(
            SimpleNamespace(
                problem_id=problem_id,
                version="v1",
                label=chr(ord("A") + index),
                time_limit_ms=1000,
                memory_limit_bytes=64_000_000,
                languages=(SimpleNamespace(id="python3"),),
            )
            for index, problem_id in enumerate(problem_ids)
        )

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(
            problem_id=problem_id,
            version=version,
            checksum="a" * 64,
        )


class MatchAPITests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.admin = User.objects.create_user(
            email="match-admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"match-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(4)
        ]
        self.tournament = Tournament.objects.create(
            title="Match API",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            participant_limit=4,
            created_by=self.admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(self.tournament.pk, player.pk, seed=index)
        self.matches = [
            item
            for item in generate_bracket(self.tournament.pk)
            if item.kind == Match.Kind.PLAYED
        ]
        self.match = self.matches[0]
        self.problem_id = uuid4()
        self.client = APIClient(enforce_csrf_checks=True)

    def login_with_csrf(self, user):
        self.client.force_login(user)
        response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_X_CSRFTOKEN=response.json()["csrfToken"])

    def configure(self, *, start_mode="manual", duration=600, problem_ids=None):
        body = {
            "problemIds": [str(item) for item in (problem_ids or [self.problem_id])],
            "matchDurationSec": duration,
            "startMode": start_mode,
        }
        with patch(
            "backend.apps.competition.views.DjangoProblemCatalog",
            return_value=ReadyTestCatalog(),
        ):
            return self.client.patch(
                f"/api/v1/matches/{self.match.pk}",
                body,
                format="json",
                HTTP_IDEMPOTENCY_KEY="config-match-1",
            )

    def test_admin_configures_real_run_and_exact_retry_is_idempotent(self):
        self.login_with_csrf(self.admin)

        first = self.configure()
        retry = self.configure()

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(first.json()["runId"], retry.json()["runId"])
        self.assertEqual(first.json()["problemVersions"], retry.json()["problemVersions"])
        payload = first.json()
        self.assertEqual(payload["matchId"], str(self.match.pk))
        self.assertEqual(payload["tournamentId"], str(self.tournament.pk))
        self.assertEqual(payload["status"], MatchRun.Status.READY)
        self.assertEqual(payload["allowedDurationMs"], 600_000)
        self.assertEqual(payload["startMode"], "manual")
        self.assertEqual(
            payload["scoringRule"]["wrongAttemptPenaltySec"],
            self.tournament.default_match_config["scoring_rule"][
                "wrong_attempt_penalty_sec"
            ],
        )
        self.assertEqual(payload["problemVersions"][0]["problemId"], str(self.problem_id))
        self.assertNotIn("checksum", str(payload))
        self.assertEqual(first["Cache-Control"], "no-store")
        self.assertEqual(MatchRun.objects.filter(match=self.match).count(), 1)

        changed = self.configure(duration=900)
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(
            MatchRun.objects.get(match=self.match).allowed_duration_ms,
            600_000,
        )

    def test_configuration_rejects_unknown_duplicate_and_invalid_fields(self):
        self.login_with_csrf(self.admin)
        base = f"/api/v1/matches/{self.match.pk}"
        valid = {
            "problemIds": [str(self.problem_id)],
            "matchDurationSec": 600,
            "startMode": "manual",
        }

        unknown = self.client.patch(
            base,
            {**valid, "winnerUserId": str(self.players[0].pk)},
            format="json",
            HTTP_IDEMPOTENCY_KEY="config-unknown",
        )
        duplicate = self.client.patch(
            base,
            {**valid, "problemIds": [str(self.problem_id), str(self.problem_id)]},
            format="json",
            HTTP_IDEMPOTENCY_KEY="config-duplicate",
        )
        string_duration = self.client.patch(
            base,
            {**valid, "matchDurationSec": "600"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="config-string-duration",
        )
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(string_duration.status_code, 400)
        self.assertFalse(MatchRun.objects.filter(match=self.match).exists())

    def test_admin_and_session_csrf_are_required_for_mutations(self):
        self.login_with_csrf(self.players[0])
        participant_attempt = self.configure()
        self.assertEqual(participant_attempt.status_code, 403)

        self.client.logout()
        no_csrf = APIClient(enforce_csrf_checks=True)
        no_csrf.force_login(self.admin)
        rejected = no_csrf.patch(
            f"/api/v1/matches/{self.match.pk}",
            {
                "problemIds": [str(self.problem_id)],
                "matchDurationSec": 600,
                "startMode": "manual",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="config-no-csrf",
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected["Cache-Control"], "no-store")

    def test_config_requires_ready_catalog_and_idempotency_key(self):
        self.login_with_csrf(self.admin)
        body = {
            "problemIds": [str(self.problem_id)],
            "matchDurationSec": 600,
            "startMode": "manual",
        }
        missing_key = self.client.patch(
            f"/api/v1/matches/{self.match.pk}", body, format="json"
        )
        self.assertEqual(missing_key.status_code, 400)

        with patch(
            "backend.apps.competition.views.DjangoProblemCatalog",
            return_value=SimpleNamespace(
                describe_ready=lambda problem_ids: (_ for _ in ()).throw(
                    LookupError("not ready")
                ),
                load_bundle=lambda problem_id, version: None,
            ),
        ):
            not_ready = self.client.patch(
                f"/api/v1/matches/{self.match.pk}",
                body,
                format="json",
                HTTP_IDEMPOTENCY_KEY="config-not-ready",
            )
        self.assertEqual(not_ready.status_code, 409)
        self.assertFalse(MatchRun.objects.filter(match=self.match).exists())

    def test_config_maps_only_sqlite_contention_to_retryable_response(self):
        self.login_with_csrf(self.admin)
        body = {
            "problemIds": [str(self.problem_id)],
            "matchDurationSec": 600,
            "startMode": "manual",
        }
        with patch(
            "backend.apps.competition.views.DjangoProblemCatalog",
            return_value=SimpleNamespace(
                describe_ready=lambda problem_ids: (_ for _ in ()).throw(
                    OperationalError("database is locked")
                ),
                load_bundle=lambda problem_id, version: None,
            ),
        ):
            busy = self.client.patch(
                f"/api/v1/matches/{self.match.pk}",
                body,
                format="json",
                HTTP_IDEMPOTENCY_KEY="config-busy",
            )
        self.assertEqual(busy.status_code, 503)
        self.assertEqual(busy.json()["error"]["code"], "match_runtime_busy")
        self.assertFalse(MatchRun.objects.filter(match=self.match).exists())

    def test_match_get_is_private_to_admin_or_an_assigned_active_participant(self):
        self.login_with_csrf(self.admin)
        configured = self.configure()
        self.assertEqual(configured.status_code, 200, configured.content)
        path = f"/api/v1/matches/{self.match.pk}"

        admin_read = self.client.get(path)
        self.assertEqual(admin_read.status_code, 200, admin_read.content)
        self.assertEqual(admin_read["Cache-Control"], "no-store")
        self.assertFalse(any(
            key in str(admin_read.json()).lower()
            for key in ("email", "source", "diagnostic", "checksum", "private")
        ))

        self.client.logout()
        anonymous = APIClient()
        self.assertEqual(anonymous.get(path).status_code, 401)

        self.client.force_login(self.admin)
        unconfigured = self.client.get(f"/api/v1/matches/{self.matches[1].pk}")
        self.assertEqual(unconfigured.status_code, 409)
        self.assertEqual(
            unconfigured.json()["error"]["code"],
            "match_run_not_configured",
        )
        self.assertEqual(unconfigured["Cache-Control"], "no-store")

        self.client.logout()
        assigned = next(
            slot.participant.user
            for slot in self.match.slots.select_related("participant__user")
            if slot.slot_index == 0
        )
        self.client.force_login(assigned)
        participant_read = self.client.get(path)
        self.assertEqual(participant_read.status_code, 200, participant_read.content)
        self.assertFalse(participant_read.json()["problemVersions"][0]["conditionAvailable"])

        self.client.logout()
        other_match_player = next(
            slot.participant.user
            for slot in self.matches[1].slots.select_related("participant__user")
            if slot.slot_index == 0
        )
        self.client.force_login(other_match_player)
        denied = self.client.get(path)
        self.assertEqual(denied.status_code, 404)

    def test_match_get_matches_v1_schema_and_computes_score_without_private_data(self):
        self.login_with_csrf(self.admin)
        configured = self.configure()
        self.assertEqual(configured.status_code, 200, configured.content)
        run = MatchRun.objects.get(match=self.match)
        now = timezone.now()
        MatchRun.objects.filter(pk=run.pk).update(
            status=MatchRun.Status.RUNNING,
            started_at=now - timedelta(seconds=40),
        )
        Match.objects.filter(pk=self.match.pk).update(status=Match.Status.RUNNING)
        run.refresh_from_db()
        participants = [
            slot.participant
            for slot in self.match.slots.select_related("participant")
        ]

        self.create_submission(run, participants[0].user, "WA", elapsed_ms=10_000)
        self.create_submission(run, participants[0].user, "OK", elapsed_ms=20_000)
        self.create_submission(run, participants[1].user, "WA", elapsed_ms=15_000)
        MatchRunReady.objects.create(run=run, participant=participants[0])

        with patch("backend.apps.competition.views.timezone.now", return_value=now):
            response = self.client.get(f"/api/v1/matches/{self.match.pk}")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        fixture = json.loads(
            (Path(__file__).resolve().parents[4] / "contracts/mvp-v1/match.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), set(fixture))
        self.assertEqual(payload["status"], MatchRun.Status.RUNNING)
        self.assertGreaterEqual(payload["elapsedMs"], 40_000)
        self.assertEqual(payload["remainingMs"], 600_000 - payload["elapsedMs"])
        self.assertEqual(payload["leaderUserId"], str(participants[0].user_id))
        self.assertEqual(payload["players"][0]["solvedCount"], 1)
        self.assertEqual(payload["players"][0]["penaltyMs"], 80_000)
        self.assertEqual(payload["players"][0]["tasks"][0]["attempts"], 2)
        self.assertEqual(payload["players"][0]["tasks"][0]["lastVerdict"], "OK")
        self.assertEqual(payload["readyUserIds"], [str(participants[0].user_id)])
        self.assertTrue(payload["problemVersions"][0]["conditionAvailable"])
        self.assertNotIn("print(1)", response.content.decode())

    def test_match_get_exposes_only_safe_infrastructure_failure_state(self):
        self.login_with_csrf(self.admin)
        configured = self.configure()
        self.assertEqual(configured.status_code, 200, configured.content)
        run = MatchRun.objects.get(match=self.match)
        started_at = timezone.now() - timedelta(seconds=40)
        MatchRun.objects.filter(pk=run.pk).update(
            status=MatchRun.Status.RUNNING,
            started_at=started_at,
        )
        Match.objects.filter(pk=self.match.pk).update(status=Match.Status.RUNNING)
        participant = self.match.slots.select_related("participant").get(slot_index=0).participant
        accepted = AttemptReceipt(
            submission_id=uuid4(),
            run_id=run.pk,
            user_id=participant.user_id,
            problem_id=self.problem_id,
            received_at=started_at + timedelta(seconds=10),
            elapsed_ms=10_000,
            scoring_version=run.scoring_version,
        )
        register_accepted(accepted)
        record_infrastructure_failure(InfrastructureFailureReceipt(
            submission_id=accepted.submission_id,
            run_id=accepted.run_id,
            reason_code="judge_infrastructure_error",
            retryable=False,
        ))

        response = self.client.get(f"/api/v1/matches/{self.match.pk}")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["resolutionRequired"])
        self.assertEqual(
            payload["infrastructureFailures"],
            [{"reasonCode": "judge_infrastructure_error", "retryable": False}],
        )
        self.assertNotIn("diagnostic", response.content.decode().lower())
        self.assertNotIn("traceback", response.content.decode().lower())

    def test_start_is_admin_only_csrf_protected_manual_and_idempotent(self):
        self.login_with_csrf(self.admin)
        configured = self.configure()
        self.assertEqual(configured.status_code, 200, configured.content)
        path = f"/api/v1/matches/{self.match.pk}/start"

        first = self.client.post(
            path, {}, format="json", HTTP_IDEMPOTENCY_KEY="start-match-1"
        )
        persisted_start = MatchRun.objects.get(match=self.match).started_at
        retry = self.client.post(
            path, {}, format="json", HTTP_IDEMPOTENCY_KEY="start-match-1"
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(first.json()["status"], MatchRun.Status.RUNNING)
        self.assertEqual(MatchRun.objects.get(match=self.match).started_at, persisted_start)

    def test_start_rejects_both_ready_and_unknown_body_fields(self):
        self.login_with_csrf(self.admin)
        configured = self.configure(start_mode="both_ready")
        self.assertEqual(configured.status_code, 200, configured.content)
        path = f"/api/v1/matches/{self.match.pk}/start"

        rejected = self.client.post(
            path,
            {"winnerUserId": str(self.players[0].pk)},
            format="json",
            HTTP_IDEMPOTENCY_KEY="start-invalid-body",
        )
        not_ready = self.client.post(
            path, {}, format="json", HTTP_IDEMPOTENCY_KEY="start-both-ready"
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(not_ready.status_code, 409)
        self.assertEqual(
            MatchRun.objects.get(match=self.match).status,
            MatchRun.Status.READY,
        )

    def create_submission(self, run, user, verdict, *, elapsed_ms):
        now = run.started_at + timedelta(milliseconds=elapsed_ms)
        submission = Submission.objects.create(
            actor=user,
            match_id=self.match.pk,
            run_id=run.pk,
            problem_id=self.problem_id,
            language_id="python3",
            source="print(1)",
            source_sha256="a" * 64,
            request_sha256="b" * 64,
            idempotency_sha256=("c" if verdict == "WA" else "d") * 64,
            received_at=now,
            elapsed_ms=elapsed_ms,
            scoring_version=run.scoring_version,
            status=Submission.Status.FINISHED,
            verdict=verdict,
            available_at=now,
        )
        accepted = register_accepted(AttemptReceipt(
            submission_id=submission.pk,
            run_id=run.pk,
            user_id=user.pk,
            problem_id=self.problem_id,
            received_at=now,
            elapsed_ms=elapsed_ms,
            scoring_version=run.scoring_version,
        ))
        apply_result(ResultReceipt(
            submission_id=accepted.submission_id,
            run_id=accepted.run_id,
            user_id=accepted.user_id,
            problem_id=accepted.problem_id,
            received_at=accepted.received_at,
            elapsed_ms=accepted.elapsed_ms,
            scoring_version=accepted.scoring_version,
            verdict=Verdict(verdict),
        ))
        return submission

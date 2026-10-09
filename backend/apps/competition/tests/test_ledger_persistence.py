from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.common.contracts import AttemptReceipt, ResultReceipt
from backend.apps.competition.domain.scoring import Verdict
from backend.apps.competition.ledger_persistence import (
    LedgerPersistenceError,
    apply_result,
    register_accepted,
)
from backend.apps.competition.models import Match, MatchRun
from backend.apps.competition.runtime import configure_match_run, mark_match_ready, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant


START = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)


class Catalog:
    def __init__(self, problem_id):
        self.problem_id = problem_id

    def describe_ready(self, problem_ids):
        return (SimpleNamespace(
            problem_id=self.problem_id,
            version="v2",
            label="A",
            time_limit_ms=1000,
            memory_limit_bytes=64_000_000,
            languages=(SimpleNamespace(id="python3"),),
        ),)

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(problem_id=problem_id, version=version, checksum="b" * 64)


class PersistedLedgerTests(TestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="ledger-admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"ledger-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        tournament = Tournament.objects.create(
            title="Ledger test",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            participant_limit=2,
            created_by=admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(tournament.pk, player.pk, seed=index)
        self.match = next(
            item for item in generate_bracket(tournament.pk)
            if item.kind == Match.Kind.PLAYED
        )
        self.problem_id = uuid4()
        self.run = configure_match_run(
            self.match.pk,
            problem_ids=[self.problem_id],
            allowed_duration_ms=600_000,
            start_mode="manual",
            scoring_rule=None,
            catalog=Catalog(self.problem_id),
        )
        start_match_run(self.run.pk, now=START)

    def accepted(self, *, submission_id=None, user=None, elapsed=30_000):
        received_at = START + timedelta(milliseconds=elapsed)
        return AttemptReceipt(
            submission_id=submission_id or uuid4(),
            run_id=self.run.pk,
            user_id=(user or self.players[0]).pk,
            problem_id=self.problem_id,
            received_at=received_at,
            elapsed_ms=elapsed,
            scoring_version=self.run.scoring_version,
        )

    def result(self, accepted, verdict):
        return ResultReceipt(
            submission_id=accepted.submission_id,
            run_id=accepted.run_id,
            user_id=accepted.user_id,
            problem_id=accepted.problem_id,
            received_at=accepted.received_at,
            elapsed_ms=accepted.elapsed_ms,
            scoring_version=accepted.scoring_version,
            verdict=verdict,
        )

    def test_acceptance_is_immutable_and_exact_retry_is_idempotent(self):
        receipt = self.accepted()

        first = register_accepted(receipt)
        retry = register_accepted(receipt)

        self.assertEqual(first.pk, retry.pk)
        self.assertEqual(self.run.accepted_attempts.count(), 1)
        with self.assertRaises(LedgerPersistenceError):
            register_accepted(self.accepted(submission_id=receipt.submission_id, elapsed=31_000))

    def test_result_is_durable_idempotent_and_updates_current_score(self):
        accepted_wa = register_accepted(self.accepted(elapsed=10_000))
        accepted_ok = register_accepted(self.accepted(elapsed=30_000))

        self.assertTrue(apply_result(self.result(accepted_wa, Verdict.WA)))
        self.assertTrue(apply_result(self.result(accepted_ok, Verdict.OK)))
        self.assertFalse(apply_result(self.result(accepted_ok, Verdict.OK)))

        run = MatchRun.objects.get(pk=self.run.pk)
        problem = run.score_snapshot["participants"][0]["problems"][0]
        self.assertEqual(problem["outcome"], "SOLVED")
        self.assertEqual(problem["lastVerdict"], "OK")
        self.assertEqual(run.score_snapshot["participants"][0]["penaltyMs"], 90_000)

    def test_conflicting_result_is_rejected(self):
        accepted = register_accepted(self.accepted())
        apply_result(self.result(accepted, Verdict.WA))

        with self.assertRaises(LedgerPersistenceError):
            apply_result(self.result(accepted, Verdict.OK))

    def test_stale_run_result_is_recorded_without_mutating_its_score(self):
        accepted = register_accepted(self.accepted())
        previous_score = MatchRun.objects.get(pk=self.run.pk).score_snapshot
        replacement = MatchRun.objects.create(
            match=self.match,
            sequence=self.run.sequence + 1,
            status=MatchRun.Status.READY,
            allowed_duration_ms=self.run.allowed_duration_ms,
            score_rule=self.run.score_rule,
            start_mode=self.run.start_mode,
            problem_versions=self.run.problem_versions,
            scoring_version=self.run.scoring_version,
        )
        self.match.current_run = replacement
        self.match.save(update_fields=("current_run",))

        self.assertFalse(apply_result(self.result(accepted, Verdict.OK)))
        run = MatchRun.objects.get(pk=self.run.pk)
        self.assertEqual(run.score_snapshot, previous_score)
        self.assertTrue(hasattr(accepted, "result"))


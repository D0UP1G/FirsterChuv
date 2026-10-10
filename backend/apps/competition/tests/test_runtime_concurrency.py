import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from django.db import connection, connections
from django.test import TransactionTestCase

from backend.apps.accounts.models import User
from backend.apps.common.contracts import AttemptReceipt, ResultReceipt
from backend.apps.competition.admin_runtime import (
    AdminCommandPersistenceBusy,
    execute_match_admin_command,
)
from backend.apps.competition.domain.scoring import Verdict
from backend.apps.competition.ledger_persistence import (
    LedgerPersistenceBusy,
    apply_result,
    register_accepted,
)
from backend.apps.competition.models import (
    AcceptedAttempt,
    AttemptResult,
    Match,
    MatchAdminCommandReceipt,
    MatchCommandReceipt,
    MatchRun,
    MatchRunReady,
)
from backend.apps.competition.runtime import (
    MatchRuntimeBusy,
    configure_match_run,
    mark_match_ready,
    start_match_run,
)
from backend.apps.competition.match_commands import execute_match_command
from backend.apps.competition.services import generate_bracket
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant


NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)


class TestCatalog:
    def __init__(self, problem_id):
        self.problem_id = problem_id

    def describe_ready(self, problem_ids):
        if tuple(problem_ids) != (self.problem_id,):
            raise ValueError("unknown problem")
        return (
            SimpleNamespace(
                problem_id=self.problem_id,
                version="v7",
                label="A",
                time_limit_ms=1000,
                memory_limit_bytes=64_000_000,
                languages=(SimpleNamespace(id="python3"),),
            ),
        )

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(problem_id=problem_id, version=version, checksum="a" * 64)


class ReadThenWaitCatalog(TestCatalog):
    def __init__(self, problem_id, match_id, barrier):
        super().__init__(problem_id)
        self.match_id = match_id
        self.barrier = barrier

    def describe_ready(self, problem_ids):
        if not Match.objects.filter(pk=self.match_id).exists():
            raise AssertionError("match disappeared during problem catalog read")
        self.barrier.wait(timeout=10)
        return super().describe_ready(problem_ids)


class MatchRuntimeConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        database_name = connection.settings_dict["NAME"]
        if (
            connection.vendor != "sqlite"
            or database_name == ":memory:"
            or "mode=memory" in database_name
        ):
            self.skipTest(
                "run with --settings=backend.apps.competition.test_settings for file-backed SQLite"
            )

        self.admin = User.objects.create_user(
            email="runtime-race-admin@example.test",
            display_name="Runtime race admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"runtime-race-player-{index}@example.test",
                display_name=f"Runtime race player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        tournament = Tournament.objects.create(
            title="Runtime race test",
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
            participant_limit=2,
            created_by=self.admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(tournament.pk, player.pk, seed=index)
        self.match = next(
            item for item in generate_bracket(tournament.pk) if item.kind == Match.Kind.PLAYED
        )
        self.problem_id = uuid4()

    def configure(self, *, mode="manual", catalog=None):
        return configure_match_run(
            self.match.pk,
            problem_ids=[self.problem_id],
            allowed_duration_ms=600_000,
            start_mode=mode,
            scoring_rule=None,
            catalog=catalog or TestCatalog(self.problem_id),
        )

    def concurrently(self, callback_for_worker, barrier):
        def run(callback):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                return callback()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run, callback_for_worker(index)) for index in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_first_configure_serializes_after_catalog_database_reads(self):
        barrier = Barrier(2)
        results = self.concurrently(
            lambda _: lambda: self.configure(
                catalog=ReadThenWaitCatalog(self.problem_id, self.match.pk, barrier)
            ),
            barrier,
        )

        self.assertEqual(results[0].pk, results[1].pk)
        self.assertEqual(MatchRun.objects.filter(match=self.match).count(), 1)
        self.assertEqual(Match.objects.get(pk=self.match.pk).current_run_id, results[0].pk)

    def test_concurrent_both_ready_updates_keep_both_signals_and_start_once(self):
        run = self.configure(mode="both_ready")
        results = self.concurrently(
            lambda index: lambda: mark_match_ready(
                run.pk, actor_user_id=self.players[index].pk, now=NOW
            ),
            Barrier(2),
        )

        stored = MatchRun.objects.get(pk=run.pk)
        self.assertEqual(stored.status, MatchRun.Status.RUNNING)
        self.assertEqual(stored.started_at, NOW)
        self.assertEqual(MatchRunReady.objects.filter(run=run).count(), 2)
        self.assertEqual({result.pk for result in results}, {run.pk})

    def test_concurrent_ready_commands_commit_both_receipts_and_start_once(self):
        run = self.configure(mode="both_ready")

        def make_command(index):
            actor = self.players[index]

            def perform(_prepared):
                ready_run = mark_match_ready(
                    run.pk, actor_user_id=actor.pk, now=NOW
                )
                return {"runId": str(ready_run.pk), "status": ready_run.status}

            return lambda: execute_match_command(
                match_id=self.match.pk,
                actor_id=actor.pk,
                action="match.ready",
                # Identical strings remain independent across participants.
                idempotency_key="ready-concurrent",
                body={},
                perform=perform,
            )

        results = self.concurrently(make_command, Barrier(2))
        stored = MatchRun.objects.get(pk=run.pk)

        self.assertEqual(stored.status, MatchRun.Status.RUNNING)
        self.assertEqual(stored.started_at, NOW)
        self.assertEqual(MatchRunReady.objects.filter(run=run).count(), 2)
        self.assertEqual(
            MatchCommandReceipt.objects.filter(
                match=self.match, action="match.ready"
            ).count(),
            2,
        )
        self.assertEqual({item["status"] for item in results}, {MatchRun.Status.READY, MatchRun.Status.RUNNING})

    def test_concurrent_start_is_idempotent_and_persists_one_transition(self):
        run = self.configure()
        results = self.concurrently(
            lambda _: lambda: start_match_run(run.pk, now=NOW),
            Barrier(2),
        )

        stored = MatchRun.objects.get(pk=run.pk)
        self.assertEqual(stored.status, MatchRun.Status.RUNNING)
        self.assertEqual(stored.started_at, NOW)
        self.assertEqual(stored.revision, run.revision + 1)
        self.assertEqual({result.pk for result in results}, {run.pk})

    def test_failed_configure_rolls_back_write_reservation(self):
        from unittest.mock import patch

        with patch(
            "backend.apps.competition.runtime.MatchRun.objects.create",
            side_effect=RuntimeError("injected run insert failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected run insert failure"):
                self.configure()

        stored = Match.objects.get(pk=self.match.pk)
        self.assertEqual(stored.status, Match.Status.WAITING)
        self.assertIsNone(stored.current_run_id)
        self.assertEqual(MatchRun.objects.filter(match=self.match).count(), 0)

    def test_exhausted_sqlite_write_contention_is_retryable_and_rolls_back(self):
        database_path = Path(connection.settings_dict["NAME"])
        blocker = sqlite3.connect(database_path, timeout=1, isolation_level=None)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            with self.assertRaises(MatchRuntimeBusy) as raised:
                self.configure()
        finally:
            blocker.rollback()
            blocker.close()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.code, "match_runtime_busy")
        self.assertNotIn("database is locked", str(raised.exception))
        stored = Match.objects.get(pk=self.match.pk)
        self.assertEqual(stored.status, Match.Status.WAITING)
        self.assertIsNone(stored.current_run_id)
        self.assertEqual(MatchRun.objects.filter(match=self.match).count(), 0)


class MatchLedgerAdminConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        database_name = connection.settings_dict["NAME"]
        if (
            connection.vendor != "sqlite"
            or database_name == ":memory:"
            or "mode=memory" in database_name
        ):
            self.skipTest(
                "run with --settings=backend.apps.competition.test_settings for file-backed SQLite"
            )
        self.admin = User.objects.create_user(
            email="ledger-race-admin@example.test",
            display_name="Ledger race admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"ledger-race-player-{index}@example.test",
                display_name=f"Ledger race player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        tournament = Tournament.objects.create(
            title="Ledger/admin race test",
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
            participant_limit=2,
            created_by=self.admin,
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
            catalog=TestCatalog(self.problem_id),
        )
        self.run = start_match_run(self.run.pk, now=NOW)

    def concurrently(self, callbacks):
        barrier = Barrier(len(callbacks))

        def run(callback):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                return callback()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(callbacks)) as executor:
            futures = [executor.submit(run, callback) for callback in callbacks]
            return [future.result(timeout=20) for future in futures]

    def accepted(self, user, *, elapsed_ms):
        return AttemptReceipt(
            submission_id=uuid4(),
            run_id=self.run.pk,
            user_id=user.pk,
            problem_id=self.problem_id,
            received_at=NOW + timedelta(milliseconds=elapsed_ms),
            elapsed_ms=elapsed_ms,
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

    def test_concurrent_different_accepted_receipts_are_both_committed(self):
        receipts = [
            self.accepted(self.players[0], elapsed_ms=10_000),
            self.accepted(self.players[1], elapsed_ms=20_000),
        ]

        results = self.concurrently([
            lambda receipt=receipt: register_accepted(receipt)
            for receipt in receipts
        ])

        self.assertEqual({item.pk for item in results}, {item.submission_id for item in receipts})
        self.assertEqual(
            AcceptedAttempt.objects.filter(run_id=self.run.pk).count(),
            2,
        )

    def test_concurrent_different_results_are_both_committed_once(self):
        accepted = [
            register_accepted(self.accepted(self.players[0], elapsed_ms=10_000)),
            register_accepted(self.accepted(self.players[1], elapsed_ms=20_000)),
        ]

        results = self.concurrently([
            lambda receipt=receipt, verdict=verdict: apply_result(
                self.result(receipt, verdict)
            )
            for receipt, verdict in zip(accepted, (Verdict.OK, Verdict.WA), strict=True)
        ])

        self.assertEqual(results, [True, True])
        self.assertEqual(
            AttemptResult.objects.filter(accepted__run_id=self.run.pk).count(),
            2,
        )

    def test_concurrent_same_admin_command_replays_exactly_once(self):
        callbacks = [
            lambda: execute_match_admin_command(
                actor_user_id=self.admin.pk,
                match_id=self.match.pk,
                command_id="same-key-pause",
                action="pause",
                reason="Concurrency regression",
                now=NOW + timedelta(seconds=5),
            )
            for _ in range(2)
        ]

        responses = self.concurrently(callbacks)

        self.assertEqual(responses[0], responses[1])
        stored = MatchRun.objects.get(pk=self.run.pk)
        self.assertEqual(stored.status, MatchRun.Status.PAUSED)
        self.assertEqual(stored.revision, self.run.revision + 1)
        self.assertEqual(
            MatchAdminCommandReceipt.objects.filter(
                match=self.match,
                command_id="same-key-pause",
            ).count(),
            1,
        )

    def test_exhausted_ledger_contention_is_retryable_and_rolls_back(self):
        accepted_receipt = self.accepted(self.players[0], elapsed_ms=10_000)
        database_path = Path(connection.settings_dict["NAME"])
        blocker = sqlite3.connect(database_path, timeout=1, isolation_level=None)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            with self.assertRaises(LedgerPersistenceBusy) as raised:
                register_accepted(accepted_receipt)
        finally:
            blocker.rollback()
            blocker.close()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertFalse(AcceptedAttempt.objects.filter(pk=accepted_receipt.submission_id).exists())
        accepted = register_accepted(accepted_receipt)

        blocker = sqlite3.connect(database_path, timeout=1, isolation_level=None)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            with self.assertRaises(LedgerPersistenceBusy):
                apply_result(self.result(accepted, Verdict.OK))
        finally:
            blocker.rollback()
            blocker.close()

        self.assertFalse(AttemptResult.objects.filter(accepted_id=accepted.pk).exists())

    def test_exhausted_admin_contention_is_retryable_and_rolls_back(self):
        database_path = Path(connection.settings_dict["NAME"])
        blocker = sqlite3.connect(database_path, timeout=1, isolation_level=None)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            with self.assertRaises(AdminCommandPersistenceBusy) as raised:
                execute_match_admin_command(
                    actor_user_id=self.admin.pk,
                    match_id=self.match.pk,
                    command_id="locked-admin-command",
                    action="pause",
                    reason="Retry later",
                    now=NOW + timedelta(seconds=5),
                )
        finally:
            blocker.rollback()
            blocker.close()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(MatchRun.objects.get(pk=self.run.pk).status, MatchRun.Status.RUNNING)
        self.assertFalse(
            MatchAdminCommandReceipt.objects.filter(command_id="locked-admin-command").exists()
        )

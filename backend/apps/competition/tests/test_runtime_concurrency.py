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
from backend.apps.competition.models import Match, MatchRun, MatchRunReady
from backend.apps.competition.runtime import (
    MatchRuntimeBusy,
    configure_match_run,
    mark_match_ready,
    start_match_run,
)
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

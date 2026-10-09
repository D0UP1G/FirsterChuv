from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.db import OperationalError
from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.competition.models import Match, MatchRun, MatchRunReady
from backend.apps.competition.runtime import (
    MatchRuntimeBusy,
    MatchRuntimeError,
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
        return (SimpleNamespace(
            problem_id=self.problem_id,
            version="v7",
            label="A",
            time_limit_ms=1000,
            memory_limit_bytes=64_000_000,
            languages=(SimpleNamespace(id="python3"),),
        ),)

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(problem_id=problem_id, version=version, checksum="a" * 64)


class PersistedMatchRuntimeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="runtime-admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"runtime-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        tournament = Tournament.objects.create(
            title="Runtime test",
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

    def configure(self, mode="manual"):
        return configure_match_run(
            self.match.pk,
            problem_ids=[self.problem_id],
            allowed_duration_ms=600_000,
            start_mode=mode,
            scoring_rule=None,
            catalog=TestCatalog(self.problem_id),
        )

    def test_configuration_pins_verified_problem_and_retries_idempotently(self):
        run = self.configure("both_ready")
        retry = self.configure("both_ready")

        self.assertEqual(run.pk, retry.pk)
        self.assertEqual(run.status, MatchRun.Status.READY)
        self.assertEqual(run.problem_versions[0]["version"], "v7")
        self.assertEqual(run.problem_versions[0]["checksum"], "a" * 64)
        self.assertEqual(run.start_mode, MatchRun.StartMode.BOTH_READY)

    def test_both_ready_persists_signals_and_starts_once(self):
        run = self.configure("both_ready")

        first = mark_match_ready(run.pk, actor_user_id=self.players[0].pk, now=NOW)
        self.assertEqual(first.status, MatchRun.Status.READY)
        second = mark_match_ready(run.pk, actor_user_id=self.players[1].pk, now=NOW)

        self.assertEqual(second.status, MatchRun.Status.RUNNING)
        self.assertEqual(second.started_at, NOW)
        self.assertEqual(MatchRunReady.objects.filter(run=run).count(), 2)
        self.assertEqual(Match.objects.get(pk=self.match.pk).status, Match.Status.RUNNING)
        retry = mark_match_ready(run.pk, actor_user_id=self.players[1].pk, now=NOW + timedelta(seconds=2))
        self.assertEqual(retry.started_at, NOW)
        self.assertEqual(MatchRunReady.objects.filter(run=run).count(), 2)

    def test_manual_ready_does_not_start_until_explicit_start(self):
        run = self.configure()
        mark_match_ready(run.pk, actor_user_id=self.players[0].pk, now=NOW)
        mark_match_ready(run.pk, actor_user_id=self.players[1].pk, now=NOW)

        ready = MatchRun.objects.get(pk=run.pk)
        self.assertEqual(ready.status, MatchRun.Status.READY)
        started = start_match_run(run.pk, now=NOW + timedelta(seconds=1))
        self.assertEqual(started.status, MatchRun.Status.RUNNING)
        self.assertEqual(started.started_at, NOW + timedelta(seconds=1))

    def test_nonparticipant_cannot_be_marked_ready(self):
        run = self.configure("both_ready")
        stranger = User.objects.create_user(
            email="stranger@example.test",
            display_name="Stranger",
            password="test-password-123456",
        )

        with self.assertRaises(MatchRuntimeError):
            mark_match_ready(run.pk, actor_user_id=stranger.pk, now=NOW)
        self.assertEqual(MatchRunReady.objects.filter(run=run).count(), 0)

    def test_manual_start_rejects_both_ready_policy(self):
        run = self.configure("both_ready")
        with self.assertRaises(MatchRuntimeError):
            start_match_run(run.pk, now=NOW)

    def test_sqlite_catalog_lock_is_retryable_but_other_db_errors_are_not_masked(self):
        with patch.object(TestCatalog, "describe_ready", side_effect=OperationalError("database is locked")):
            with self.assertRaises(MatchRuntimeBusy) as raised:
                self.configure()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(MatchRun.objects.filter(match=self.match).count(), 0)

        with patch.object(TestCatalog, "describe_ready", side_effect=OperationalError("disk I/O error")):
            with self.assertRaisesRegex(OperationalError, "disk I/O error"):
                self.configure()
        self.assertEqual(MatchRun.objects.filter(match=self.match).count(), 0)

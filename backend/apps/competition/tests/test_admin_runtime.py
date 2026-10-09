from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.competition.admin_runtime import (
    AdminCommandPersistenceError,
    execute_match_admin_command,
)
from backend.apps.competition.models import Match, MatchAdminCommandReceipt, MatchRun
from backend.apps.competition.runtime import configure_match_run, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant
from backend.apps.competition.tests.test_runtime import TestCatalog


START = datetime(2026, 10, 10, 11, 0, tzinfo=timezone.utc)


class PersistedAdminClockCommandsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="actions-admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"actions-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        tournament = Tournament.objects.create(
            title="Admin actions",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            participant_limit=2,
            created_by=self.admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(tournament.pk, player.pk, seed=index)
        self.match = next(
            item for item in generate_bracket(tournament.pk)
            if item.kind == Match.Kind.PLAYED
        )
        problem_id = uuid4()
        self.run = configure_match_run(
            self.match.pk,
            problem_ids=[problem_id],
            allowed_duration_ms=600_000,
            start_mode="manual",
            scoring_rule=None,
            catalog=TestCatalog(problem_id),
        )
        start_match_run(self.run.pk, now=START)

    def command(self, *, key, action, reason=None, seconds=None, actor=None, now=None):
        return execute_match_admin_command(
            actor_user_id=(actor or self.admin).pk,
            match_id=self.match.pk,
            command_id=key,
            action=action,
            reason=reason,
            seconds=seconds,
            now=now,
        )

    def test_pause_resume_and_exact_replay_persist_clock_once(self):
        pause_at = START + timedelta(seconds=5)
        paused = self.command(key="pause-1", action="pause", reason="Safety pause", now=pause_at)
        resumed = self.command(key="resume-1", action="resume", now=pause_at + timedelta(seconds=3))
        replay = self.command(key="pause-1", action="pause", reason="Safety pause", now=pause_at)

        run = MatchRun.objects.get(pk=self.run.pk)
        self.assertEqual(paused["status"], MatchRun.Status.PAUSED)
        self.assertEqual(resumed["status"], MatchRun.Status.RUNNING)
        self.assertEqual(replay, paused)
        self.assertEqual(run.accumulated_pause_ms, 3000)
        self.assertEqual(run.revision, 3)
        self.assertEqual(MatchAdminCommandReceipt.objects.filter(match=self.match).count(), 2)

    def test_extension_has_server_policy_bound_and_requires_reason(self):
        result = self.command(
            key="extend-1",
            action="extend",
            reason="Network outage",
            seconds=120,
            now=START + timedelta(seconds=4),
        )
        self.assertEqual(result["allowedDurationMs"], 720_000)
        with self.assertRaises(AdminCommandPersistenceError):
            self.command(key="extend-2", action="extend", reason="Too long", seconds=601)
        with self.assertRaises(AdminCommandPersistenceError):
            self.command(key="extend-3", action="extend", seconds=20)

    def test_command_id_reuse_with_different_intent_is_rejected(self):
        self.command(key="pause-reused", action="pause", reason="First", now=START + timedelta(seconds=1))
        with self.assertRaises(AdminCommandPersistenceError):
            self.command(key="pause-reused", action="pause", reason="Different", now=START + timedelta(seconds=2))

    def test_inactive_or_non_admin_actor_is_rejected(self):
        self.admin.is_active = False
        self.admin.save(update_fields=("is_active",))
        with self.assertRaises(AdminCommandPersistenceError):
            self.command(key="pause-inactive", action="pause", reason="Reason", now=START + timedelta(seconds=1))

        player = User.objects.get(pk=self.players[0].pk)
        with self.assertRaises(AdminCommandPersistenceError):
            self.command(key="pause-player", action="pause", reason="Reason", actor=player, now=START + timedelta(seconds=1))


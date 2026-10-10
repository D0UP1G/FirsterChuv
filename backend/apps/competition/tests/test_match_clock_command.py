from datetime import timedelta
from io import StringIO
from uuid import uuid4
from types import SimpleNamespace

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.competition.models import Match, MatchRun
from backend.apps.competition.runtime import configure_match_run, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.events.models import MatchEvent
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant


class Catalog:
    def __init__(self, problem_id):
        self.problem_id = problem_id

    def describe_ready(self, problem_ids):
        return (SimpleNamespace(
            problem_id=self.problem_id,
            version="clock-v1",
            label="A",
            time_limit_ms=1000,
            memory_limit_bytes=64_000_000,
            languages=(SimpleNamespace(id="python3"),),
        ),)

    def load_bundle(self, problem_id, version):
        return SimpleNamespace(problem_id=problem_id, version=version, checksum="d" * 64)


class MatchClockCommandTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="clock-command-admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        players = [
            User.objects.create_user(
                email=f"clock-command-player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        now = timezone.now()
        tournament = Tournament.objects.create(
            title="Clock command",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            participant_limit=2,
            created_by=self.admin,
        )
        for index, player in enumerate(players, start=1):
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

    def start(self, *, age):
        return start_match_run(self.run.pk, now=timezone.now() - age)

    def test_one_shot_pass_finalizes_expired_current_run_and_is_idempotent(self):
        self.start(age=timedelta(minutes=11))
        output = StringIO()

        call_command("run_match_clock", "--once", stdout=output)
        run = MatchRun.objects.get(pk=self.run.pk)
        self.match.refresh_from_db()
        self.assertEqual(run.status, MatchRun.Status.TIED)
        self.assertEqual(self.match.status, Match.Status.TIED)
        self.assertEqual(MatchEvent.objects.filter(match_id=self.match.pk).count(), 1)
        self.assertIn("Reconciled 1 match run(s).", output.getvalue())

        call_command("run_match_clock", "--once", stdout=StringIO())
        self.assertEqual(MatchEvent.objects.filter(match_id=self.match.pk).count(), 1)

    def test_one_shot_pass_leaves_unexpired_run_running(self):
        self.start(age=timedelta(seconds=30))
        output = StringIO()

        call_command("run_match_clock", "--once", stdout=output)

        self.assertEqual(MatchRun.objects.get(pk=self.run.pk).status, MatchRun.Status.RUNNING)
        self.assertIn("Reconciled 0 match run(s).", output.getvalue())

    def test_poll_interval_has_a_bounded_policy(self):
        with self.assertRaises(CommandError):
            call_command("run_match_clock", "--interval-ms", "1", "--once")

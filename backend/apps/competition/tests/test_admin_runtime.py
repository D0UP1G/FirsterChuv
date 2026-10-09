from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.competition.admin_runtime import (
    AdminCommandPersistenceError,
    execute_match_admin_command,
)
from backend.apps.competition.models import Match, MatchAdminCommandReceipt, MatchRun, MatchSlot
from backend.apps.competition.runtime import configure_match_run, start_match_run
from backend.apps.competition.services import generate_bracket
from backend.apps.tournaments.models import Tournament, TournamentParticipant
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

    def command(
        self, *, key, action, reason=None, seconds=None, winner_user_id=None,
        old_user_id=None, replacement_user_id=None, actor=None, now=None,
    ):
        return execute_match_admin_command(
            actor_user_id=(actor or self.admin).pk,
            match_id=self.match.pk,
            command_id=key,
            action=action,
            reason=reason,
            seconds=seconds,
            winner_user_id=winner_user_id,
            old_user_id=old_user_id,
            replacement_user_id=replacement_user_id,
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

    def test_technical_result_records_winner_and_exact_retry(self):
        winner_id = self.players[0].pk
        result = self.command(
            key="technical-result-1",
            action="technical_result",
            reason="Opponent withdrew",
            winner_user_id=winner_id,
            now=START + timedelta(seconds=30),
        )
        replay = self.command(
            key="technical-result-1",
            action="technical_result",
            reason="Opponent withdrew",
            winner_user_id=winner_id,
            now=START + timedelta(seconds=31),
        )

        run = MatchRun.objects.get(pk=self.run.pk)
        match = Match.objects.get(pk=self.match.pk)
        self.assertEqual(result, replay)
        self.assertEqual(run.status, MatchRun.Status.FINISHED)
        self.assertEqual(run.winner.user_id, winner_id)
        self.assertEqual(run.technical_reason, "Opponent withdrew")
        self.assertEqual(match.winner_id, run.winner_id)

    def test_rematch_supersedes_history_and_starts_clean_run(self):
        self.run.score_snapshot = {"old": "score"}
        self.run.save(update_fields=("score_snapshot",))

        response = self.command(
            key="rematch-1",
            action="rematch",
            reason="Final was tied",
            now=START + timedelta(seconds=60),
        )

        self.run.refresh_from_db()
        match = Match.objects.get(pk=self.match.pk)
        new_run = match.current_run
        self.assertEqual(self.run.status, MatchRun.Status.SUPERSEDED)
        self.assertEqual(new_run.sequence, self.run.sequence + 1)
        self.assertEqual(new_run.status, MatchRun.Status.READY)
        self.assertEqual(new_run.score_snapshot, {})
        self.assertEqual(new_run.problem_versions, self.run.problem_versions)
        self.assertEqual(response["runId"], str(new_run.pk))
        receipt = MatchAdminCommandReceipt.objects.get(command_id="rematch-1")
        self.assertEqual(receipt.run_id, self.run.pk)

    def test_technical_winner_advances_into_the_reserved_downstream_slot(self):
        tournament = Tournament.objects.create(
            title="Four player actions",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            participant_limit=4,
            created_by=self.admin,
        )
        extra_players = [
            User.objects.create_user(
                email=f"actions-extra-{index}@example.test",
                display_name=f"Extra {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        for index, player in enumerate((*self.players, *extra_players), start=1):
            assign_participant(tournament.pk, player.pk, seed=index)
        matches = generate_bracket(tournament.pk)
        opening = next(
            match for match in matches
            if match.kind == Match.Kind.PLAYED and match.round_index == 0
        )
        problem_id = uuid4()
        run = configure_match_run(
            opening.pk,
            problem_ids=[problem_id],
            allowed_duration_ms=600_000,
            start_mode="manual",
            scoring_rule=None,
            catalog=TestCatalog(problem_id),
        )
        start_match_run(run.pk, now=START)
        winner_id = opening.slots.get(slot_index=0).participant.user_id

        execute_match_admin_command(
            actor_user_id=self.admin.pk,
            match_id=opening.pk,
            command_id="technical-advance-1",
            action="technical_result",
            reason="Opponent withdrew",
            winner_user_id=winner_id,
            now=START + timedelta(seconds=20),
        )

        downstream_slot = MatchSlot.objects.get(
            match_id=opening.next_match_id,
            slot_index=opening.next_slot,
        )
        self.assertEqual(downstream_slot.participant.user_id, winner_id)
        self.assertEqual(downstream_slot.resolution, MatchSlot.Resolution.PLAYER)

    def test_running_replacement_preserves_old_run_identity_and_starts_clean_run(self):
        old_slot = self.match.slots.select_related("participant").get(slot_index=0)
        old_user_id = old_slot.participant.user_id
        replacement = User.objects.create_user(
            email="replacement-running@example.test",
            display_name="Replacement",
            password="test-password-123456",
        )
        original_ids = list(self.run.participant_user_ids)
        self.run.score_snapshot = {"old": "score"}
        self.run.save(update_fields=("score_snapshot",))

        result = self.command(
            key="replace-running-1",
            action="replace_participant",
            reason="Participant withdrew",
            old_user_id=old_user_id,
            replacement_user_id=replacement.pk,
            now=START + timedelta(seconds=10),
        )

        self.run.refresh_from_db()
        self.match.refresh_from_db()
        slot = self.match.slots.get(slot_index=0)
        replacement_entry = TournamentParticipant.objects.get(
            tournament=self.match.tournament,
            user=replacement,
        )
        self.assertEqual(self.run.status, MatchRun.Status.SUPERSEDED)
        self.assertEqual(self.run.participant_user_ids, original_ids)
        self.assertEqual(slot.participant_id, replacement_entry.pk)
        self.assertEqual(replacement_entry.status, TournamentParticipant.Status.ACTIVE)
        self.assertEqual(result["status"], MatchRun.Status.READY)
        self.assertEqual(result["runId"], str(self.match.current_run_id))
        self.assertEqual(self.match.current_run.participant_user_ids[0], str(replacement.pk))
        self.assertEqual(self.match.current_run.score_snapshot, {})
        self.assertEqual(
            TournamentParticipant.objects.get(tournament=self.match.tournament, user_id=old_user_id).status,
            TournamentParticipant.Status.REMOVED,
        )

    def test_ready_replacement_updates_frozen_roster_and_exact_replay(self):
        self.run.status = MatchRun.Status.READY
        self.run.started_at = None
        self.run.save(update_fields=("status", "started_at"))
        self.match.status = Match.Status.READY
        self.match.save(update_fields=("status",))
        old_user_id = self.match.slots.get(slot_index=1).participant.user_id
        replacement = User.objects.create_user(
            email="replacement-ready@example.test",
            display_name="Replacement Ready",
            password="test-password-123456",
        )
        args = dict(
            key="replace-ready-1",
            action="replace_participant",
            reason="Scheduling conflict",
            old_user_id=old_user_id,
            replacement_user_id=replacement.pk,
        )

        response = self.command(**args)
        replay = self.command(**args)

        self.run.refresh_from_db()
        self.assertEqual(response, replay)
        self.assertEqual(self.run.status, MatchRun.Status.READY)
        self.assertEqual(self.run.participant_user_ids[1], str(replacement.pk))
        self.assertEqual(
            self.match.slots.get(slot_index=1).participant.user_id,
            replacement.pk,
        )
        self.assertEqual(MatchAdminCommandReceipt.objects.filter(command_id=args["key"]).count(), 1)

    def test_waiting_replacement_without_run_persists_nullable_receipt(self):
        self.match.current_run = None
        self.match.status = Match.Status.WAITING
        self.match.save(update_fields=("current_run", "status"))
        old_user_id = self.match.slots.get(slot_index=0).participant.user_id
        replacement = User.objects.create_user(
            email="replacement-waiting@example.test",
            display_name="Replacement Waiting",
            password="test-password-123456",
        )

        response = self.command(
            key="replace-waiting-1",
            action="replace_participant",
            reason="Unavailable before match",
            old_user_id=old_user_id,
            replacement_user_id=replacement.pk,
        )

        receipt = MatchAdminCommandReceipt.objects.get(command_id="replace-waiting-1")
        self.assertIsNone(response["runId"])
        self.assertIsNone(receipt.run_id)
        self.assertEqual(response["status"], MatchRun.Status.WAITING)
        self.assertEqual(self.match.slots.get(slot_index=0).participant.user_id, replacement.pk)


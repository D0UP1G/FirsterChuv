from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.competition.domain.bracket import BracketInputError
from backend.apps.competition.models import Match, MatchRun, MatchSlot
from backend.apps.competition.services import (
    BracketPersistenceError,
    BracketResetConflict,
    generate_bracket,
    reset_bracket,
    set_first_round_pairings,
)
from backend.apps.tournaments.models import Tournament, TournamentParticipant
from backend.apps.tournaments.services import assign_participant, set_participant_seed


class PersistBracketTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )

    def create_tournament(
        self, suffix: str, count: int
    ) -> tuple[Tournament, list[TournamentParticipant]]:
        now = timezone.now()
        tournament = Tournament.objects.create(
            title=f"Bracket {suffix}",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            participant_limit=max(2, count),
            created_by=self.admin,
        )
        roster = []
        for index in range(count):
            user = User.objects.create_user(
                email=f"{suffix}-player-{index}@example.test",
                display_name=f"{suffix} player {index}",
                password="test-password-123456",
            )
            entry, _ = assign_participant(
                tournament.pk,
                user.pk,
                seed=index + 1,
            )
            roster.append(entry)
        return tournament, roster

    def test_generation_persists_matches_slots_advancement_and_byes(self):
        tournament, roster = self.create_tournament("three", 3)

        matches = generate_bracket(tournament.pk)

        tournament.refresh_from_db()
        self.assertIsNotNone(tournament.roster_frozen_at)
        self.assertEqual(len(matches), 3)
        self.assertEqual(MatchSlot.objects.filter(match__tournament=tournament).count(), 6)
        self.assertEqual(MatchRun.objects.filter(match__tournament=tournament).count(), 0)

        byes = [match for match in matches if match.kind == Match.Kind.BYE]
        played_nodes = [match for match in matches if match.kind == Match.Kind.PLAYED]
        self.assertEqual(len(byes), 1)
        self.assertEqual(len(played_nodes), 2)
        bye = byes[0]
        self.assertEqual(bye.status, Match.Status.BYE)
        self.assertIn(bye.winner_id, {entry.pk for entry in roster})
        self.assertEqual(
            list(bye.slots.order_by("slot_index").values_list("resolution", flat=True)).count(
                MatchSlot.Resolution.BYE
            ),
            1,
        )

        final = next(match for match in played_nodes if match.round_index == 1)
        slots = list(final.slots.order_by("slot_index"))
        self.assertEqual(slots[0].resolution, MatchSlot.Resolution.PLAYER)
        self.assertEqual(slots[0].upstream_match_id, bye.pk)
        self.assertEqual(slots[1].resolution, MatchSlot.Resolution.WAITING)
        self.assertEqual(slots[1].upstream_match.next_match_id, final.pk)

        first_round = [match for match in matches if match.round_index == 0]
        self.assertTrue(all(match.next_match_id == final.pk for match in first_round))
        self.assertEqual({match.next_slot for match in first_round}, {0, 1})

    def test_generation_uses_frozen_canonical_order_without_writing_null_seeds(self):
        tournament, roster = self.create_tournament("unseeded", 3)
        for entry in roster:
            set_participant_seed(tournament.pk, entry.user_id, seed=None)
        canonical_ids = list(
            TournamentParticipant.objects.filter(tournament=tournament)
            .order_by("user_id")
            .values_list("pk", flat=True)
        )

        matches = generate_bracket(tournament.pk)

        first_round_ids = [
            slot.participant_id
            for match in matches
            if match.round_index == 0
            for slot in match.slots.all()
            if slot.resolution == MatchSlot.Resolution.PLAYER
        ]
        self.assertCountEqual(first_round_ids, canonical_ids)
        self.assertTrue(
            all(
                entry.seed is None
                for entry in TournamentParticipant.objects.filter(tournament=tournament)
            )
        )

    def test_generation_is_idempotent_and_does_not_duplicate_matches(self):
        tournament, _ = self.create_tournament("idempotent", 5)

        first = generate_bracket(tournament.pk)
        first_ids = [match.pk for match in first]
        frozen_at = Tournament.objects.get(pk=tournament.pk).roster_frozen_at
        second = generate_bracket(tournament.pk)

        self.assertEqual([match.pk for match in second], first_ids)
        self.assertEqual(Match.objects.filter(tournament=tournament).count(), len(first_ids))
        self.assertEqual(
            Tournament.objects.get(pk=tournament.pk).roster_frozen_at,
            frozen_at,
        )

    def test_generation_checks_no_player_occurs_twice_per_round(self):
        for count in range(2, 9):
            with self.subTest(count=count):
                tournament, _ = self.create_tournament(f"count-{count}", count)
                matches = generate_bracket(tournament.pk)
                round_indices = {match.round_index for match in matches}

                for round_index in round_indices:
                    with self.subTest(round_index=round_index):
                        participant_ids = [
                            slot.participant_id
                            for match in matches
                            if match.round_index == round_index
                            for slot in match.slots.all()
                            if slot.resolution == MatchSlot.Resolution.PLAYER
                        ]
                        self.assertEqual(
                            len(participant_ids),
                            len(set(participant_ids)),
                        )

    def test_generation_failure_rolls_back_roster_freeze(self):
        tournament, _ = self.create_tournament("rollback", 4)

        with patch(
            "backend.apps.competition.services.generate_single_elimination",
            side_effect=BracketInputError("forced failure"),
        ):
            with self.assertRaises(BracketInputError):
                generate_bracket(tournament.pk)

        tournament.refresh_from_db()
        self.assertIsNone(tournament.roster_frozen_at)
        self.assertEqual(Match.objects.filter(tournament=tournament).count(), 0)

    def test_explicit_reset_rebuilds_same_frozen_roster_before_start(self):
        tournament, roster = self.create_tournament("reset", 4)
        first = generate_bracket(tournament.pk)
        original_ids = {match.pk for match in first}
        frozen_at = Tournament.objects.get(pk=tournament.pk).roster_frozen_at

        rebuilt = reset_bracket(tournament.pk)

        self.assertTrue(original_ids.isdisjoint({match.pk for match in rebuilt}))
        self.assertEqual(len(rebuilt), len(first))
        self.assertEqual(
            set(
                MatchSlot.objects.filter(
                    match__tournament=tournament,
                    match__round_index=0,
                    resolution=MatchSlot.Resolution.PLAYER,
                ).values_list("participant_id", flat=True)
            ),
            {entry.pk for entry in roster},
        )
        self.assertEqual(
            Tournament.objects.get(pk=tournament.pk).roster_frozen_at,
            frozen_at,
        )

    def test_reset_is_rejected_once_a_match_run_started(self):
        tournament, _ = self.create_tournament("started", 2)
        first_match = next(
            match
            for match in generate_bracket(tournament.pk)
            if match.kind == Match.Kind.PLAYED
        )
        run = MatchRun.objects.create(
            match=first_match,
            sequence=1,
            status=MatchRun.Status.RUNNING,
            started_at=timezone.now(),
            allowed_duration_ms=60_000,
        )
        first_match.current_run = run
        first_match.status = Match.Status.RUNNING
        first_match.save(update_fields=("current_run", "status", "updated_at"))
        original_count = Match.objects.filter(tournament=tournament).count()

        with self.assertRaises(BracketResetConflict):
            reset_bracket(tournament.pk)

        self.assertEqual(Match.objects.filter(tournament=tournament).count(), original_count)
        self.assertEqual(MatchRun.objects.filter(match__tournament=tournament).count(), 1)

    def test_manual_first_round_pairings_preserve_bye_advancement(self):
        tournament, roster = self.create_tournament("manual", 3)
        generate_bracket(tournament.pk)
        pairings = (
            (str(roster[0].pk), str(roster[1].pk)),
            (str(roster[2].pk), None),
        )

        matches = set_first_round_pairings(tournament.pk, pairings)

        first_round = [match for match in matches if match.round_index == 0]
        final = next(match for match in matches if match.round_index == 1)
        self.assertEqual(len(first_round), 2)
        played = next(match for match in first_round if match.kind == Match.Kind.PLAYED)
        bye = next(match for match in first_round if match.kind == Match.Kind.BYE)
        self.assertEqual(
            list(
                played.slots.order_by("slot_index").values_list(
                    "participant_id", flat=True
                )
            ),
            [roster[0].pk, roster[1].pk],
        )
        self.assertEqual(bye.winner_id, roster[2].pk)
        self.assertEqual(
            {slot.participant_id for slot in final.slots.all() if slot.participant_id},
            {roster[2].pk},
        )
        self.assertIn(bye.pk, {slot.upstream_match_id for slot in final.slots.all()})
        self.assertEqual(played.next_match_id, final.pk)
        self.assertEqual(bye.next_match_id, final.pk)

    def test_invalid_manual_pairings_leave_existing_bracket_untouched(self):
        tournament, roster = self.create_tournament("manual-invalid", 4)
        original = generate_bracket(tournament.pk)
        original_ids = [match.pk for match in original]
        original_slots = list(
            MatchSlot.objects.filter(match__tournament=tournament)
            .order_by("match__round_index", "match__position", "slot_index")
            .values_list("match__bracket_key", "slot_index", "participant_id")
        )
        pairings = (
            (str(roster[0].pk), str(roster[1].pk)),
            (str(roster[2].pk), str(roster[0].pk)),
        )

        with self.assertRaises(BracketInputError):
            set_first_round_pairings(tournament.pk, pairings)

        self.assertEqual(
            list(
                Match.objects.filter(tournament=tournament)
                .order_by("round_index", "position", "id")
                .values_list("pk", flat=True)
            ),
            original_ids,
        )
        self.assertEqual(
            list(
                MatchSlot.objects.filter(match__tournament=tournament)
                .order_by("match__round_index", "match__position", "slot_index")
                .values_list("match__bracket_key", "slot_index", "participant_id")
            ),
            original_slots,
        )

    def test_generation_rejects_an_existing_unfrozen_bracket_record(self):
        tournament, roster = self.create_tournament("unfrozen", 2)
        Match.objects.create(
            tournament=tournament,
            bracket_key="r1-p1",
            round_index=0,
            position=0,
            kind=Match.Kind.PLAYED,
        )
        for index in range(2):
            MatchSlot.objects.create(
                match=Match.objects.get(tournament=tournament),
                slot_index=index,
                resolution=MatchSlot.Resolution.PLAYER,
                participant=roster[index],
            )

        with self.assertRaises(BracketPersistenceError):
            generate_bracket(tournament.pk)

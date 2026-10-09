"""API and lifecycle checks for the tournament management slice."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import transaction
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from django.test import TestCase, TransactionTestCase

from backend.apps.accounts.models import User
from backend.apps.tournaments.models import Tournament, TournamentParticipant
from backend.apps.tournaments.serializers import TournamentSerializer
from backend.apps.tournaments.services import (
    RosterInvariantViolation,
    RosterMutationError,
    RosterNotReady,
    assign_participant,
    freeze_roster,
    remove_participant,
    set_participant_seed,
)


def tournament_payload(**overrides):
    now = timezone.now().replace(microsecond=0)
    payload = {
        "title": "Чувашский блиц 2026",
        "description": "Первый турнир",
        "startsAt": now.isoformat().replace("+00:00", "Z"),
        "endsAt": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "format": "single_elimination",
        "participantLimit": 16,
        "visibility": "public",
        "matchDurationSec": 1200,
        "startMode": "manual",
        "scoringRule": {
            "order": ["solved_desc", "penalty_asc", "last_accepted_asc"],
            "wrongAttemptPenaltySec": 60,
            "penalizedVerdicts": ["WA", "TL", "ML", "RE"],
            "finalTiePolicy": "rematch",
        },
    }
    payload.update(overrides)
    return payload


class TournamentAPITests(TestCase):
    list_url = "/api/v1/tournaments"

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.test",
            display_name="Admin",
            password="valid-test-password-123",
            role=User.Roles.ADMIN,
        )
        self.participant = User.objects.create_user(
            email="player@example.test",
            display_name="Player",
            password="valid-test-password-123",
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def authenticate(self, user):
        self.client.force_login(user)
        token_response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(token_response.status_code, 200)
        self.client.credentials(HTTP_X_CSRFTOKEN=token_response.json()["csrfToken"])

    def create_tournament(self, *, participant_limit=4, frozen=False):
        now = timezone.now()
        return Tournament.objects.create(
            title="Roster Tournament",
            description="",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            participant_limit=participant_limit,
            created_by=self.admin,
            roster_frozen_at=now if frozen else None,
        )

    def add_user(self, email, display_name, **fields):
        return User.objects.create_user(
            email=email,
            display_name=display_name,
            password="valid-test-password-123",
            **fields,
        )

    def test_admin_can_create_list_read_and_patch_a_tournament(self):
        self.authenticate(self.admin)

        created = self.client.post(self.list_url, tournament_payload(), format="json")

        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        self.assertEqual(body["title"], "Чувашский блиц 2026")
        self.assertEqual(body["format"], "single_elimination")
        self.assertEqual(body["participantLimit"], 16)
        self.assertEqual(body["status"], Tournament.Status.DRAFT)
        self.assertEqual(body["createdBy"], str(self.admin.id))
        self.assertTrue(body["slug"].isascii())
        self.assertTrue(body["slug"].endswith(body["id"].replace("-", "")[:12]))
        self.assertEqual(body["matchDurationSec"], 1200)
        self.assertEqual(body["scoringRule"]["wrongAttemptPenaltySec"], 60)
        self.assertEqual(created["Cache-Control"], "no-store")

        tournament_id = body["id"]
        listed = self.client.get(self.list_url)
        retrieved = self.client.get(f"{self.list_url}/{tournament_id}")
        patched = self.client.patch(
            f"{self.list_url}/{tournament_id}",
            {"title": "Обновлённый блиц", "visibility": "unlisted"},
            format="json",
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)
        self.assertEqual(len(listed.json()["results"]), 1)
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(patched.status_code, 200, patched.content)
        self.assertEqual(patched.json()["title"], "Обновлённый блиц")
        self.assertEqual(patched.json()["visibility"], "unlisted")

    def test_create_rejects_invalid_dates_cap_format_visibility_and_unknown_fields(self):
        self.authenticate(self.admin)
        payload = tournament_payload()
        payload["endsAt"] = payload["startsAt"]
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, 400)

        for field, value in (
            ("participantLimit", 1),
            ("format", "double_elimination"),
            ("visibility", "private"),
            ("role", "admin"),
            ("createdBy", str(self.participant.id)),
            ("status", "running"),
        ):
            with self.subTest(field=field):
                response = self.client.post(
                    self.list_url,
                    tournament_payload(**{field: value}),
                    format="json",
                )
                self.assertEqual(response.status_code, 400, response.content)

    def test_match_config_is_validated_and_defaults_are_documented(self):
        self.authenticate(self.admin)
        invalid_duration = self.client.post(
            self.list_url,
            tournament_payload(matchDurationSec=59),
            format="json",
        )
        invalid_rule = self.client.post(
            self.list_url,
            tournament_payload(
                scoringRule={
                    "order": ["penalty_asc", "solved_desc", "last_accepted_asc"],
                }
            ),
            format="json",
        )
        self.assertEqual(invalid_duration.status_code, 400)
        self.assertEqual(invalid_rule.status_code, 400)

        payload = tournament_payload()
        payload.pop("matchDurationSec")
        payload.pop("startMode")
        payload.pop("scoringRule")
        created = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["matchDurationSec"], 1200)
        self.assertEqual(created.json()["startMode"], "manual")

    def test_participant_and_anonymous_cannot_create_or_edit(self):
        response = self.client.post(self.list_url, tournament_payload(), format="json")
        self.assertNotEqual(response.status_code, 201)

        self.authenticate(self.participant)
        response = self.client.post(self.list_url, tournament_payload(), format="json")
        self.assertEqual(response.status_code, 403)

        tournament = Tournament.objects.create(
            title="Closed",
            description="",
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1),
            participant_limit=4,
            created_by=self.admin,
        )
        response = self.client.patch(
            f"{self.list_url}/{tournament.id}",
            {"title": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_mutations_require_csrf_and_reject_mass_assignment(self):
        self.client.force_login(self.admin)
        no_csrf = self.client.post(self.list_url, tournament_payload(), format="json")
        self.assertEqual(no_csrf.status_code, 403)

        self.authenticate(self.admin)
        response = self.client.post(
            self.list_url,
            tournament_payload(isStaff=True, isSuperuser=True),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_respects_roster_freeze_and_terminal_status(self):
        self.authenticate(self.admin)
        create = self.client.post(self.list_url, tournament_payload(), format="json")
        tournament_id = create.json()["id"]
        tournament = Tournament.objects.get(pk=tournament_id)
        tournament.roster_frozen_at = timezone.now()
        tournament.save(update_fields=("roster_frozen_at",))

        frozen_config = self.client.patch(
            f"{self.list_url}/{tournament_id}",
            {"participantLimit": 32},
            format="json",
        )
        metadata = self.client.patch(
            f"{self.list_url}/{tournament_id}",
            {"title": "Name remains editable"},
            format="json",
        )
        self.assertEqual(frozen_config.status_code, 400)
        self.assertEqual(metadata.status_code, 200, metadata.content)

        tournament.status = Tournament.Status.RUNNING
        tournament.save(update_fields=("status",))
        terminal_update = self.client.patch(
            f"{self.list_url}/{tournament_id}",
            {"description": "No longer editable"},
            format="json",
        )
        self.assertEqual(terminal_update.status_code, 400)

    def test_delete_draft_removes_it_but_delete_after_freeze_archives(self):
        self.authenticate(self.admin)
        draft = self.client.post(self.list_url, tournament_payload(), format="json")
        draft_id = draft.json()["id"]
        deleted = self.client.delete(f"{self.list_url}/{draft_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Tournament.objects.filter(pk=draft_id).exists())

        frozen = Tournament.objects.create(
            title="Frozen",
            description="",
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1),
            participant_limit=4,
            created_by=self.admin,
            roster_frozen_at=timezone.now(),
        )
        archived = self.client.delete(f"{self.list_url}/{frozen.id}")
        frozen.refresh_from_db()
        self.assertEqual(archived.status_code, 204)
        self.assertEqual(frozen.status, Tournament.Status.ARCHIVED)

    def test_assign_is_idempotent_remove_is_logical_and_reassignment_reuses_entry(self):
        tournament = self.create_tournament()
        second = self.add_user("second@example.test", "Second Player")
        self.authenticate(self.admin)
        collection_url = f"{self.list_url}/{tournament.id}/participants"

        assigned = self.client.post(
            collection_url,
            {"userId": str(self.participant.id), "seed": 1},
            format="json",
        )
        repeated = self.client.post(
            collection_url,
            {"userId": str(self.participant.id), "seed": 1},
            format="json",
        )
        other_added = self.client.post(
            collection_url,
            {"userId": str(second.id), "seed": 3},
            format="json",
        )
        self.assertEqual(assigned.status_code, 201, assigned.content)
        self.assertEqual(repeated.status_code, 200, repeated.content)
        self.assertEqual(other_added.status_code, 201, other_added.content)
        self.assertEqual(assigned.json()["userId"], str(self.participant.id))
        self.assertEqual(tournament.participants.count(), 2)
        tournament.refresh_from_db()
        self.assertEqual(tournament.active_participant_count, 2)

        remove_url = f"{collection_url}/{self.participant.id}"
        removed = self.client.delete(remove_url)
        repeated_remove = self.client.delete(remove_url)
        entry = TournamentParticipant.objects.get(tournament=tournament, user=self.participant)
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(repeated_remove.status_code, 204)
        self.assertEqual(entry.status, TournamentParticipant.Status.REMOVED)
        self.assertIsNotNone(entry.removed_at)
        tournament.refresh_from_db()
        self.assertEqual(tournament.active_participant_count, 1)

        reassigned = self.client.post(
            collection_url,
            {"userId": str(self.participant.id), "seed": 2},
            format="json",
        )
        entry.refresh_from_db()
        tournament.refresh_from_db()
        self.assertEqual(reassigned.status_code, 201, reassigned.content)
        self.assertEqual(tournament.participants.count(), 2)
        self.assertEqual(entry.status, TournamentParticipant.Status.ACTIVE)
        self.assertEqual(entry.seed, 2)
        self.assertIsNone(entry.removed_at)
        self.assertEqual(tournament.active_participant_count, 2)

    def test_capacity_seed_uniqueness_and_active_participant_role_are_enforced(self):
        tournament = self.create_tournament(participant_limit=2)
        second = self.add_user("second@example.test", "Second Player")
        third = self.add_user("third@example.test", "Third Player")
        inactive = self.add_user(
            "inactive@example.test",
            "Inactive Player",
            is_active=False,
        )
        self.authenticate(self.admin)
        collection_url = f"{self.list_url}/{tournament.id}/participants"

        first_added = self.client.post(
            collection_url,
            {"userId": str(self.participant.id), "seed": 1},
            format="json",
        )
        duplicate_seed = self.client.post(
            collection_url,
            {"userId": str(second.id), "seed": 1},
            format="json",
        )
        second_added = self.client.post(
            collection_url,
            {"userId": str(second.id), "seed": 2},
            format="json",
        )
        over_capacity = self.client.post(
            collection_url,
            {"userId": str(third.id), "seed": 3},
            format="json",
        )
        admin_as_player = self.client.post(
            collection_url,
            {"userId": str(self.admin.id)},
            format="json",
        )
        inactive_as_player = self.client.post(
            collection_url,
            {"userId": str(inactive.id)},
            format="json",
        )
        invalid_seed = self.client.post(
            collection_url,
            {"userId": str(third.id), "seed": 2147483648},
            format="json",
        )

        self.assertEqual(first_added.status_code, 201, first_added.content)
        self.assertEqual(duplicate_seed.status_code, 409)
        self.assertEqual(second_added.status_code, 201, second_added.content)
        self.assertEqual(over_capacity.status_code, 409)
        self.assertEqual(admin_as_player.status_code, 400)
        self.assertEqual(inactive_as_player.status_code, 400)
        self.assertEqual(invalid_seed.status_code, 400)
        duplicate_at_capacity = self.client.post(
            collection_url,
            {"userId": str(self.participant.id), "seed": 1},
            format="json",
        )
        self.assertEqual(duplicate_at_capacity.status_code, 200)
        tournament.refresh_from_db()
        self.assertEqual(tournament.active_participant_count, 2)
        self.assertEqual(
            tournament.participants.filter(status=TournamentParticipant.Status.ACTIVE).count(),
            2,
        )

    def test_seed_patch_rejects_duplicate_and_can_clear_seed(self):
        tournament = self.create_tournament()
        second = self.add_user("second@example.test", "Second Player")
        TournamentParticipant.objects.create(
            tournament=tournament,
            user=self.participant,
            seed=1,
        )
        TournamentParticipant.objects.create(
            tournament=tournament,
            user=second,
            seed=2,
        )
        tournament.active_participant_count = 2
        tournament.save(update_fields=("active_participant_count",))
        self.authenticate(self.admin)
        participant_url = f"{self.list_url}/{tournament.id}/participants/{self.participant.id}"

        duplicate = self.client.patch(participant_url, {"seed": 2}, format="json")
        clear = self.client.patch(participant_url, {"seed": None}, format="json")

        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(clear.status_code, 200, clear.content)
        self.assertIsNone(
            TournamentParticipant.objects.get(tournament=tournament, user=self.participant).seed
        )

    def test_participant_reads_only_joined_tournaments_and_safe_roster_fields(self):
        joined = self.create_tournament()
        private_to_other = self.create_tournament()
        TournamentParticipant.objects.create(tournament=joined, user=self.participant, seed=1)
        joined.active_participant_count = 1
        joined.save(update_fields=("active_participant_count",))
        self.authenticate(self.participant)

        listing = self.client.get(self.list_url)
        own = self.client.get(f"{self.list_url}/{joined.id}")
        other = self.client.get(f"{self.list_url}/{private_to_other.id}")
        participants = self.client.get(f"{self.list_url}/{joined.id}/participants")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)
        self.assertEqual(participants.status_code, 200)
        self.assertEqual(participants.json()["count"], 1)
        row = participants.json()["results"][0]
        self.assertEqual(row["displayName"], self.participant.display_name)
        self.assertNotIn("email", row)
        self.assertEqual(row["status"], TournamentParticipant.Status.ACTIVE)

    def test_roster_changes_are_rejected_after_freeze(self):
        tournament = self.create_tournament(frozen=True)
        self.authenticate(self.admin)
        collection_url = f"{self.list_url}/{tournament.id}/participants"
        assigned = self.client.post(
            collection_url,
            {"userId": str(self.participant.id), "seed": 1},
            format="json",
        )
        tournament.refresh_from_db()
        self.assertEqual(assigned.status_code, 409)
        self.assertEqual(tournament.active_participant_count, 0)

    def test_admin_user_directory_is_minimal_active_participant_only_and_bounded(self):
        self.add_user("other@example.test", "Other Player")
        self.add_user("inactive@example.test", "Inactive Player", is_active=False)
        self.add_user("admin2@example.test", "Second Admin", role=User.Roles.ADMIN)
        self.authenticate(self.admin)

        response = self.client.get("/api/v1/admin/users", {"q": "player", "limit": 1})
        invalid_role = self.client.get("/api/v1/admin/users", {"role": "admin"})
        long_search = self.client.get("/api/v1/admin/users", {"q": "x" * 81})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(set(response.json()["results"][0]), {"id", "displayName"})
        self.assertNotIn("email", response.json()["results"][0])
        self.assertEqual(invalid_role.status_code, 400)
        self.assertEqual(long_search.status_code, 400)


class RosterFreezeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="freeze-admin@example.test",
            display_name="Freeze Admin",
            password="valid-test-password-123",
            role=User.Roles.ADMIN,
        )
        self.first = User.objects.create_user(
            email="freeze-one@example.test",
            display_name="First Player",
            password="valid-test-password-123",
        )
        self.second = User.objects.create_user(
            email="freeze-two@example.test",
            display_name="Second Player",
            password="valid-test-password-123",
        )
        self.third = User.objects.create_user(
            email="freeze-three@example.test",
            display_name="Third Player",
            password="valid-test-password-123",
        )
        now = timezone.now()
        self.tournament = Tournament.objects.create(
            title="Freeze test",
            description="",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            participant_limit=4,
            created_by=self.admin,
        )

    def test_freeze_is_idempotent_and_returns_seeded_then_unseeded_roster(self):
        assign_participant(self.tournament.id, self.second.id)
        assign_participant(self.tournament.id, self.first.id, seed=1)

        roster = freeze_roster(self.tournament.id)
        self.tournament.refresh_from_db()
        frozen_at = self.tournament.roster_frozen_at
        repeated_roster = freeze_roster(self.tournament.id)
        self.tournament.refresh_from_db()

        self.assertEqual([entry.user_id for entry in roster], [self.first.id, self.second.id])
        self.assertEqual(
            [entry.id for entry in repeated_roster],
            [entry.id for entry in roster],
        )
        self.assertEqual(self.tournament.roster_frozen_at, frozen_at)

        with self.assertRaises(RosterMutationError):
            assign_participant(self.tournament.id, self.third.id)
        with self.assertRaises(RosterMutationError):
            set_participant_seed(self.tournament.id, self.first.id, 2)
        with self.assertRaises(RosterMutationError):
            remove_participant(self.tournament.id, self.first.id)

    def test_freeze_requires_two_active_rows_and_consistent_count(self):
        with self.assertRaises(RosterNotReady):
            freeze_roster(self.tournament.id)

        assign_participant(self.tournament.id, self.first.id)
        with self.assertRaises(RosterNotReady):
            freeze_roster(self.tournament.id)
        self.tournament.refresh_from_db()
        self.assertIsNone(self.tournament.roster_frozen_at)

        Tournament.objects.filter(pk=self.tournament.id).update(active_participant_count=2)
        with self.assertRaises(RosterInvariantViolation):
            freeze_roster(self.tournament.id)
        self.tournament.refresh_from_db()
        self.assertIsNone(self.tournament.roster_frozen_at)

    def test_outer_bracket_transaction_rollback_also_rolls_back_freeze(self):
        assign_participant(self.tournament.id, self.first.id)
        assign_participant(self.tournament.id, self.second.id)

        with self.assertRaisesMessage(RuntimeError, "simulated bracket failure"):
            with transaction.atomic():
                roster = freeze_roster(self.tournament.id)
                self.assertEqual(len(roster), 2)
                self.tournament.refresh_from_db()
                self.assertIsNotNone(self.tournament.roster_frozen_at)
                raise RuntimeError("simulated bracket failure")

        self.tournament.refresh_from_db()
        self.assertIsNone(self.tournament.roster_frozen_at)
        self.assertEqual(self.tournament.active_participant_count, 2)

    def test_stale_tournament_patch_cannot_change_roster_config_after_freeze(self):
        assign_participant(self.tournament.id, self.first.id, seed=1)
        assign_participant(self.tournament.id, self.second.id, seed=2)
        stale_instance = Tournament.objects.get(pk=self.tournament.id)
        freeze_roster(self.tournament.id)

        serializer = TournamentSerializer(
            stale_instance,
            data={"participant_limit": 8},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(RosterMutationError):
            serializer.save()
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.participant_limit, 4)


class RosterCapacityConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_simultaneous_assignments_never_exceed_capacity(self):
        admin = User.objects.create_user(
            email="concurrent-admin@example.test",
            display_name="Concurrent Admin",
            password="valid-test-password-123",
            role=User.Roles.ADMIN,
        )
        players = [
            User.objects.create_user(
                email=f"concurrent-{index}@example.test",
                display_name=f"Concurrent Player {index}",
                password="valid-test-password-123",
            )
            for index in range(3)
        ]
        now = timezone.now()
        tournament = Tournament.objects.create(
            title="Concurrent roster",
            description="",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            participant_limit=2,
            created_by=admin,
        )
        barrier = Barrier(len(players))

        def assign(player, seed):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    entry, created = assign_participant(
                        tournament.id,
                        player.id,
                        seed=seed,
                    )
                    return ("assigned", entry.id, created)
                except RosterMutationError as error:
                    return ("rejected", error.code)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(players)) as executor:
            futures = [
                executor.submit(assign, player, index + 1)
                for index, player in enumerate(players)
            ]
            results = [future.result(timeout=20) for future in futures]

        tournament.refresh_from_db()
        active_count = tournament.participants.filter(
            status=TournamentParticipant.Status.ACTIVE
        ).count()
        self.assertEqual(sum(result[0] == "assigned" for result in results), 2, results)
        self.assertEqual(sum(result[0] == "rejected" for result in results), 1, results)
        self.assertEqual(tournament.active_participant_count, 2)
        self.assertEqual(active_count, 2)

    def test_assignment_racing_freeze_is_either_in_roster_or_rejected(self):
        admin = User.objects.create_user(
            email="freeze-race-admin@example.test",
            display_name="Freeze Race Admin",
            password="valid-test-password-123",
            role=User.Roles.ADMIN,
        )
        players = [
            User.objects.create_user(
                email=f"freeze-race-{index}@example.test",
                display_name=f"Freeze Race Player {index}",
                password="valid-test-password-123",
            )
            for index in range(3)
        ]
        now = timezone.now()
        tournament = Tournament.objects.create(
            title="Freeze assignment race",
            description="",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            participant_limit=4,
            created_by=admin,
        )
        assign_participant(tournament.id, players[0].id, seed=1)
        assign_participant(tournament.id, players[1].id, seed=2)
        barrier = Barrier(2)

        def add_last_player():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    entry, created = assign_participant(tournament.id, players[2].id, seed=3)
                    return ("assigned", entry.id, created)
                except RosterMutationError as error:
                    return ("rejected", error.code)
            finally:
                close_old_connections()

        def freeze():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                entries = freeze_roster(tournament.id)
                return {entry.user_id for entry in entries}
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            add_future = executor.submit(add_last_player)
            freeze_future = executor.submit(freeze)
            assignment_result = add_future.result(timeout=20)
            frozen_user_ids = freeze_future.result(timeout=20)

        tournament.refresh_from_db()
        active_user_ids = set(
            tournament.participants.filter(status=TournamentParticipant.Status.ACTIVE)
            .values_list("user_id", flat=True)
        )
        self.assertIn(assignment_result[0], {"assigned", "rejected"})
        self.assertEqual(frozen_user_ids, active_user_ids)
        self.assertEqual(len(active_user_ids), tournament.active_participant_count)
        self.assertIsNotNone(tournament.roster_frozen_at)

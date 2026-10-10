from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.competition.bracket_commands import execute_bracket_command
from backend.apps.competition.models import BracketCommandReceipt, Match, MatchRun
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant


class BracketAPITests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.admin = User.objects.create_user(
            email="admin@example.test",
            display_name="Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.players = [
            User.objects.create_user(
                email=f"player-{index}@example.test",
                display_name=f"Player {index}",
                password="test-password-123456",
            )
            for index in range(3)
        ]
        self.outsider = User.objects.create_user(
            email="outsider@example.test",
            display_name="Outsider",
            password="test-password-123456",
        )
        self.tournament = Tournament.objects.create(
            title="Bracket API",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            participant_limit=4,
            created_by=self.admin,
        )
        for index, player in enumerate(self.players, start=1):
            assign_participant(self.tournament.pk, player.pk, seed=index)
        self.client = APIClient(enforce_csrf_checks=True)

    def login_with_csrf(self, user):
        self.client.force_login(user)
        response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_X_CSRFTOKEN=response.json()["csrfToken"])

    def generate_bracket(self):
        return self.client.post(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket/generate",
            {"seedingMode": "manual"},
            format="json",
        )

    def pairings_body(self, first_pair=(0, 1), bye_player=2):
        left, right = first_pair
        remaining_player = bye_player
        return {
            "pairings": [
                {
                    "position": 0,
                    "leftUserId": str(self.players[left].pk),
                    "rightUserId": str(self.players[right].pk),
                },
                {
                    "position": 1,
                    "leftUserId": str(self.players[remaining_player].pk),
                    "rightUserId": None,
                },
            ],
            "reason": "Manual pairing update",
        }

    def set_pairings(self, *, key, body=None):
        return self.client.put(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket/pairings",
            body or self.pairings_body(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_admin_generates_and_reads_allowlisted_bracket_dto(self):
        self.login_with_csrf(self.admin)
        response = self.client.post(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket/generate",
            {"seedingMode": "manual"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["tournamentId"], str(self.tournament.pk))
        self.assertEqual(payload["bracketSize"], 4)
        self.assertTrue(payload["rosterFrozenAt"])
        self.assertEqual(len(payload["matches"]), 3)
        self.assertIn("nextMatchId", payload["matches"][0])
        self.assertTrue(all("email" not in str(match).lower() for match in payload["matches"]))
        self.assertEqual(response["Cache-Control"], "no-store")

        bracket = self.client.get(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket"
        )
        self.assertEqual(bracket.status_code, 200, bracket.content)
        self.assertEqual(bracket.json(), payload)

    def test_generation_requires_admin_csrf_and_supported_request_fields(self):
        url = f"/api/v1/tournaments/{self.tournament.pk}/bracket/generate"
        self.login_with_csrf(self.players[0])
        forbidden = self.client.post(url, {"seedingMode": "manual"}, format="json")
        self.assertEqual(forbidden.status_code, 403)
        self.client.logout()

        no_csrf_client = APIClient(enforce_csrf_checks=True)
        no_csrf_client.force_login(self.admin)
        csrf_rejected = no_csrf_client.post(
            url,
            {"seedingMode": "manual"},
            format="json",
        )
        self.assertEqual(csrf_rejected.status_code, 403)

        self.login_with_csrf(self.admin)
        missing_mode = self.client.post(url, {}, format="json")
        unsupported_mode = self.client.post(
            url,
            {"seedingMode": "rating"},
            format="json",
        )
        extra_field = self.client.post(
            url,
            {"seedingMode": "manual", "roster": []},
            format="json",
        )
        self.assertEqual(missing_mode.status_code, 400)
        self.assertEqual(unsupported_mode.status_code, 400)
        self.assertEqual(extra_field.status_code, 400)
        self.assertEqual(Match.objects.filter(tournament=self.tournament).count(), 0)

    def test_generation_returns_conflict_for_closed_tournament_without_freezing(self):
        self.login_with_csrf(self.admin)
        url = f"/api/v1/tournaments/{self.tournament.pk}/bracket/generate"
        original_roster = list(
            self.tournament.participants.order_by("id").values_list(
                "id", "user_id", "seed", "status", "removed_at"
            )
        )

        for lifecycle_status in (
            Tournament.Status.RUNNING,
            Tournament.Status.COMPLETED,
            Tournament.Status.ARCHIVED,
        ):
            with self.subTest(status=lifecycle_status):
                Tournament.objects.filter(pk=self.tournament.pk).update(
                    status=lifecycle_status
                )
                response = self.client.post(
                    url,
                    {"seedingMode": "manual"},
                    format="json",
                )

                self.assertEqual(response.status_code, 409, response.content)
                self.assertEqual(
                    response.json()["error"]["code"],
                    "tournament_not_editable",
                )
                self.tournament.refresh_from_db()
                self.assertIsNone(self.tournament.roster_frozen_at)
                self.assertEqual(
                    self.tournament.status,
                    lifecycle_status,
                )
                self.assertEqual(
                    list(
                        self.tournament.participants.order_by("id").values_list(
                            "id", "user_id", "seed", "status", "removed_at"
                        )
                    ),
                    original_roster,
                )
                self.assertFalse(Match.objects.filter(tournament=self.tournament).exists())

    def test_only_admin_or_joined_active_participant_can_read_bracket(self):
        self.login_with_csrf(self.admin)
        generated = self.client.post(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket/generate",
            {"seedingMode": "manual"},
            format="json",
        )
        self.assertEqual(generated.status_code, 200, generated.content)

        self.client.logout()
        self.client.force_login(self.players[0])
        joined_read = self.client.get(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket"
        )
        self.assertEqual(joined_read.status_code, 200)

        self.client.logout()
        self.client.force_login(self.outsider)
        outsider_read = self.client.get(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket"
        )
        self.assertEqual(outsider_read.status_code, 404)

    def test_manual_pairings_use_user_ids_and_rebuild_byes_atomically(self):
        self.login_with_csrf(self.admin)
        generated = self.generate_bracket()
        self.assertEqual(generated.status_code, 200, generated.content)

        response = self.set_pairings(key="pairings-command-1")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Cache-Control"], "no-store")
        first_round = sorted(
            (
                match
                for match in response.json()["matches"]
                if match["roundIndex"] == 0
            ),
            key=lambda match: match["position"],
        )
        self.assertEqual(len(first_round), 2)
        self.assertEqual(
            [
                slot["participant"]["userId"] if slot["participant"] else None
                for slot in first_round[0]["slots"]
            ],
            [str(self.players[0].pk), str(self.players[1].pk)],
        )
        self.assertEqual(first_round[1]["kind"], "BYE")
        self.assertEqual(
            [slot["participant"]["userId"] if slot["participant"] else None
             for slot in first_round[1]["slots"]],
            [str(self.players[2].pk), None],
        )
        self.assertEqual(
            BracketCommandReceipt.objects.filter(tournament=self.tournament).count(),
            1,
        )
        receipt = BracketCommandReceipt.objects.get(tournament=self.tournament)
        self.assertNotEqual(receipt.idempotency_sha256, "pairings-command-1")
        self.assertEqual(len(receipt.idempotency_sha256), 64)
        self.assertEqual(receipt.actor_id, self.admin.pk)
        self.assertEqual(receipt.reason, "Manual pairing update")

    def test_pairing_command_requires_admin_csrf_key_and_exact_request_shape(self):
        url = f"/api/v1/tournaments/{self.tournament.pk}/bracket/pairings"
        body = self.pairings_body()
        self.login_with_csrf(self.players[0])
        denied = self.client.put(url, body, format="json", HTTP_IDEMPOTENCY_KEY="denied")
        self.assertEqual(denied.status_code, 403)

        self.client.logout()
        no_csrf_client = APIClient(enforce_csrf_checks=True)
        no_csrf_client.force_login(self.admin)
        no_csrf = no_csrf_client.put(
            url,
            body,
            format="json",
            HTTP_IDEMPOTENCY_KEY="no-csrf",
        )
        self.assertEqual(no_csrf.status_code, 403)

        self.login_with_csrf(self.admin)
        missing_key = self.client.put(url, body, format="json")
        extra_field = dict(body, actorId=str(self.admin.pk))
        extra = self.client.put(
            url,
            extra_field,
            format="json",
            HTTP_IDEMPOTENCY_KEY="extra-field",
        )
        bad_positions = self.pairings_body()
        bad_positions["pairings"][1]["position"] = 3
        invalid_position = self.set_pairings(key="bad-position", body=bad_positions)

        self.assertEqual(missing_key.status_code, 400)
        self.assertEqual(extra.status_code, 400)
        self.assertEqual(invalid_position.status_code, 400)
        self.assertEqual(BracketCommandReceipt.objects.count(), 0)
        self.assertFalse(Match.objects.filter(tournament=self.tournament).exists())

    def test_pairing_idempotency_replays_original_result_and_rejects_changed_intent(self):
        self.login_with_csrf(self.admin)
        self.assertEqual(self.generate_bracket().status_code, 200)
        original_body = self.pairings_body()
        first = self.set_pairings(key="pairing-idempotency", body=original_body)
        self.assertEqual(first.status_code, 200, first.content)

        changed_body = self.pairings_body(first_pair=(0, 2), bye_player=1)
        changed = self.set_pairings(key="pairing-second-command", body=changed_body)
        self.assertEqual(changed.status_code, 200, changed.content)
        current = self.client.get(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket"
        ).json()
        self.assertEqual(current, changed.json())

        retry = self.set_pairings(key="pairing-idempotency", body=original_body)
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(
            self.client.get(
                f"/api/v1/tournaments/{self.tournament.pk}/bracket"
            ).json(),
            current,
        )

        conflicting_body = self.pairings_body(first_pair=(1, 2), bye_player=0)
        conflict = self.set_pairings(
            key="pairing-idempotency",
            body=conflicting_body,
        )
        self.assertEqual(conflict.status_code, 409, conflict.content)
        self.assertEqual(conflict.json()["error"]["code"], "idempotency_conflict")
        self.assertEqual(
            self.client.get(
                f"/api/v1/tournaments/{self.tournament.pk}/bracket"
            ).json(),
            current,
        )

    def test_pairings_reject_non_roster_or_repeated_users_without_mutation(self):
        self.login_with_csrf(self.admin)
        self.assertEqual(self.generate_bracket().status_code, 200)
        original = self.client.get(
            f"/api/v1/tournaments/{self.tournament.pk}/bracket"
        ).json()

        repeated = self.pairings_body()
        repeated["pairings"][1]["leftUserId"] = str(self.players[0].pk)
        duplicate = self.set_pairings(key="duplicate-player", body=repeated)

        unknown = self.pairings_body()
        unknown["pairings"][0]["leftUserId"] = str(self.outsider.pk)
        unavailable = self.set_pairings(key="unknown-player", body=unknown)

        self.assertEqual(duplicate.status_code, 400, duplicate.content)
        self.assertEqual(unavailable.status_code, 400, unavailable.content)
        self.assertEqual(
            self.client.get(
                f"/api/v1/tournaments/{self.tournament.pk}/bracket"
            ).json(),
            original,
        )
        self.assertEqual(BracketCommandReceipt.objects.count(), 0)

    def test_reset_replays_original_bracket_and_new_reset_fails_after_start(self):
        self.login_with_csrf(self.admin)
        self.assertEqual(self.generate_bracket().status_code, 200)
        self.assertEqual(self.set_pairings(key="before-reset").status_code, 200)
        reset_url = f"/api/v1/tournaments/{self.tournament.pk}/bracket/reset"
        request_body = {"reason": "Rebuild before match start"}
        reset = self.client.post(
            reset_url,
            request_body,
            format="json",
            HTTP_IDEMPOTENCY_KEY="reset-command",
        )
        self.assertEqual(reset.status_code, 200, reset.content)

        first_match = Match.objects.filter(
            tournament=self.tournament,
            kind=Match.Kind.PLAYED,
        ).first()
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
        current_match_ids = set(
            Match.objects.filter(tournament=self.tournament).values_list("id", flat=True)
        )

        exact_retry = self.client.post(
            reset_url,
            request_body,
            format="json",
            HTTP_IDEMPOTENCY_KEY="reset-command",
        )
        rejected_new_reset = self.client.post(
            reset_url,
            {"reason": "A new reset after start"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="reset-after-start",
        )

        self.assertEqual(exact_retry.status_code, 200, exact_retry.content)
        self.assertEqual(exact_retry.json(), reset.json())
        self.assertEqual(rejected_new_reset.status_code, 409, rejected_new_reset.content)
        self.assertEqual(
            set(Match.objects.filter(tournament=self.tournament).values_list("id", flat=True)),
            current_match_ids,
        )
        self.assertEqual(BracketCommandReceipt.objects.count(), 2)

    def test_command_transaction_claims_tournament_before_receipt_reads(self):
        with CaptureQueriesContext(connection) as captured:
            response = execute_bracket_command(
                tournament_id=self.tournament.pk,
                actor_id=self.admin.pk,
                action=BracketCommandReceipt.Action.RESET,
                idempotency_key="capture-first-write",
                reason="Capture SQL order",
                arguments={},
                perform=lambda: {"accepted": True},
            )

        statements = [
            query["sql"].strip()
            for query in captured
            if query["sql"].lstrip().upper().startswith(
                ("SELECT", "UPDATE", "INSERT", "DELETE")
            )
        ]
        self.assertEqual(response, {"accepted": True})
        self.assertTrue(statements)
        self.assertTrue(statements[0].upper().startswith("UPDATE"), statements)
        self.assertIn("TOURNAMENTS_TOURNAMENT", statements[0].upper())


class BracketCommandConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        now = timezone.now()
        self.admin = User.objects.create_user(
            email="race-admin@example.test",
            display_name="Race Admin",
            password="test-password-123456",
            role=User.Roles.ADMIN,
        )
        self.tournament = Tournament.objects.create(
            title="Bracket command race",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            participant_limit=4,
            created_by=self.admin,
        )
        self.barrier = Barrier(2)
        self.side_effect_lock = Lock()
        self.side_effect_count = 0

    def perform_once(self):
        with self.side_effect_lock:
            self.side_effect_count += 1
        return {"accepted": True, "tournamentId": str(self.tournament.pk)}

    def execute_concurrently(self):
        def execute():
            close_old_connections()
            try:
                self.barrier.wait(timeout=10)
                return execute_bracket_command(
                    tournament_id=self.tournament.pk,
                    actor_id=self.admin.pk,
                    action=BracketCommandReceipt.Action.RESET,
                    idempotency_key="concurrent-reset-key",
                    reason="Concurrent retry",
                    arguments={},
                    perform=self.perform_once,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(execute) for _ in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_concurrent_exact_retry_runs_effect_once_and_replays_receipt(self):
        responses = self.execute_concurrently()

        self.assertEqual(responses[0], responses[1])
        self.assertEqual(self.side_effect_count, 1)
        self.assertEqual(BracketCommandReceipt.objects.count(), 1)

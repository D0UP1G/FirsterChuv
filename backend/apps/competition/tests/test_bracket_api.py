from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.competition.models import Match
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

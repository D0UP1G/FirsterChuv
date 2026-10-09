"""API and lifecycle checks for the tournament management slice."""

from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.tournaments.models import Tournament


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

import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.competition.models import Match
from backend.apps.competition.services import generate_bracket
from backend.apps.events import public_views
from backend.apps.events.models import MatchEvent
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import assign_participant

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[3] / "contracts/mvp-v1/score-event.json").read_text(encoding="utf-8")
)


def read_stream(response) -> str:
    return b"".join(response.streaming_content).decode("utf-8")


@override_settings(
    PUBLIC_SSE_POLL_SECONDS=0.01,
    PUBLIC_SSE_HEARTBEAT_SECONDS=0.02,
    PUBLIC_SSE_MAX_SECONDS=0.15,
)
class PublicTournamentViewsTests(TestCase):
    def setUp(self):
        public_views._open_streams = 0
        now = timezone.now()
        self.admin = User.objects.create_user(
            email="public-views-admin@example.test", display_name="Admin",
            password="test-password-123456", role=User.Roles.ADMIN,
        )
        players = [
            User.objects.create_user(
                email=f"public-views-player-{index}@example.test", display_name=f"Игрок {index}",
                password="test-password-123456",
            )
            for index in range(2)
        ]
        self.tournament = Tournament.objects.create(
            title="Публичный турнир", starts_at=now, ends_at=now + timedelta(hours=2),
            participant_limit=2, created_by=self.admin, visibility=Tournament.Visibility.PUBLIC,
            status=Tournament.Status.SCHEDULED,
        )
        for index, player in enumerate(players, start=1):
            assign_participant(self.tournament.pk, player.pk, seed=index)
        self.match = next(item for item in generate_bracket(self.tournament.pk) if item.kind == Match.Kind.PLAYED)
        self.client = APIClient()

    def add_event(self, match=None):
        match = match or self.match
        return MatchEvent.objects.create(
            tournament_id=self.tournament.pk, match_id=match.pk, run_id=FIXTURE["runId"],
            event_type=MatchEvent.Types.SCORE_CHANGED, payload=FIXTURE["payload"],
        )

    def test_list_shows_only_public_published_tournaments_without_private_fields(self):
        now = timezone.now()
        for title, visibility, status in (
            ("Черновик", Tournament.Visibility.PUBLIC, Tournament.Status.DRAFT),
            ("По ссылке", Tournament.Visibility.UNLISTED, Tournament.Status.SCHEDULED),
        ):
            Tournament.objects.create(
                title=title, starts_at=now, ends_at=now + timedelta(hours=1), participant_limit=2,
                created_by=self.admin, visibility=visibility, status=status,
            )
        response = self.client.get("/api/v1/public/tournaments")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["title"] for item in body["results"]], ["Публичный турнир"])
        self.assertEqual(set(body["results"][0]), {"id", "title", "status", "startsAt", "endsAt"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_bracket_is_anonymous_and_carries_names_but_no_account_identifiers(self):
        response = self.client.get(f"/api/v1/public/tournaments/{self.tournament.pk}/bracket")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"tournamentId", "title", "bracketSize", "matches"})
        self.assertEqual(body["bracketSize"], 2)
        match = body["matches"][0]
        self.assertEqual(set(match), {"id", "key", "roundIndex", "position", "status", "slots", "winnerName"})
        self.assertEqual({slot["displayName"] for slot in match["slots"]}, {"Игрок 0", "Игрок 1"})
        self.assertNotIn("userId", json.dumps(body))
        self.assertNotIn("@", json.dumps(body))

    def test_unlisted_bracket_is_hidden_and_unknown_tournament_is_not_found(self):
        Tournament.objects.filter(pk=self.tournament.pk).update(visibility=Tournament.Visibility.UNLISTED)
        self.assertEqual(self.client.get(f"/api/v1/public/tournaments/{self.tournament.pk}/bracket").status_code, 404)
        missing = "/api/v1/public/tournaments/00000000-0000-4000-8000-0000000000ee/bracket"
        self.assertEqual(self.client.get(missing).status_code, 404)

    def test_stream_sends_events_after_the_cursor_with_ids_and_a_heartbeat(self):
        first = self.add_event()
        second = self.add_event()

        response = self.client.get(
            f"/api/v1/public/matches/{self.match.pk}/events", HTTP_LAST_EVENT_ID=str(first.pk)
        )
        text = read_stream(response)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn(f"id: {second.pk}\n", text)
        self.assertNotIn(f"id: {first.pk}\n", text)
        self.assertIn("event: score.changed", text)
        self.assertIn(": heartbeat", text)
        data_line = next(line for line in text.splitlines() if line.startswith("data: {"))
        self.assertEqual(json.loads(data_line[6:])["type"], "score.changed")

    def test_stream_requests_resync_when_the_cursor_is_ahead_of_the_durable_log(self):
        response = self.client.get(
            f"/api/v1/public/matches/{self.match.pk}/events", HTTP_LAST_EVENT_ID="999999"
        )
        self.assertIn("event: stream.resync_required", read_stream(response))

    def test_stream_rejects_invalid_cursor_and_hidden_tournaments(self):
        url = f"/api/v1/public/matches/{self.match.pk}/events"
        self.assertEqual(self.client.get(url, HTTP_LAST_EVENT_ID="abc").status_code, 404)
        Tournament.objects.filter(pk=self.tournament.pk).update(visibility=Tournament.Visibility.UNLISTED)
        self.assertEqual(self.client.get(url).status_code, 404)

    @override_settings(PUBLIC_SSE_MAX_STREAMS=1)
    def test_stream_capacity_is_bounded_and_released_when_the_stream_ends(self):
        url = f"/api/v1/public/matches/{self.match.pk}/events"
        first = self.client.get(url)
        self.assertEqual(self.client.get(url).status_code, 503)
        read_stream(first)
        self.assertEqual(public_views._open_streams, 0)
        again = self.client.get(url)
        self.assertEqual(again.status_code, 200)
        read_stream(again)

    @override_settings(PUBLIC_SSE_MAX_STREAMS=1)
    def test_slot_is_freed_when_the_client_leaves_before_reading_anything(self):
        url = f"/api/v1/public/matches/{self.match.pk}/events"
        abandoned = self.client.get(url)
        self.assertEqual(public_views._open_streams, 1)
        abandoned.close()
        self.assertEqual(public_views._open_streams, 0)
        abandoned.close()
        self.assertEqual(public_views._open_streams, 0)

    def test_stream_accepts_the_event_stream_accept_header_sent_by_browsers(self):
        response = self.client.get(
            f"/api/v1/public/matches/{self.match.pk}/events", HTTP_ACCEPT="text/event-stream"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))
        read_stream(response)
        hidden = self.client.get(
            "/api/v1/public/matches/00000000-0000-4000-8000-0000000000ee/events",
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(hidden.status_code, 404)

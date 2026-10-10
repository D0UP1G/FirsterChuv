"""Anonymous public tournament list, bracket and live event stream (SSE).

Everything here is read-only and public-safe: no account identifiers, e-mail, source code or
private diagnostics. Unlisted tournaments need the hashed share token header.
"""

from __future__ import annotations

import json
import threading
import time

from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.common.throttles import RemoteAddressScopedRateThrottle
from backend.apps.competition.models import Match
from backend.apps.competition.views import bracket_match_queryset
from backend.apps.events.access import DjangoPublicAccess, PublicAccessDenied
from backend.apps.events.public_payloads import PublicEventInputError
from backend.apps.events.services import current_event_cursor, read_match_events_after
from backend.apps.tournaments.models import Tournament

MAX_LIST_LIMIT = 50
SHARE_TOKEN_HEADER = "X-Tournament-Share-Token"

_stream_slots_lock = threading.Lock()
_open_streams = 0


class StreamCapacityExceeded(APIException):
    status_code = 503
    default_code = "public_stream_capacity"
    default_detail = "Слишком много зрителей онлайн, повторите позже."


def _setting(name: str, default):
    return getattr(settings, name, default)


class PublicReadView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RemoteAddressScopedRateThrottle]
    throttle_scope = "public_snapshot"

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def assert_public(self, request, tournament_id):
        try:
            DjangoPublicAccess().assert_can_view(
                tournament_id, share_token=request.headers.get(SHARE_TOKEN_HEADER)
            )
        except PublicAccessDenied as error:
            raise NotFound("Публичный объект не найден.") from error


class PublicTournamentListView(PublicReadView):
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "25"))
            offset = int(request.query_params.get("offset", "0"))
        except ValueError:
            limit, offset = 25, 0
        limit = max(1, min(limit, MAX_LIST_LIMIT))
        offset = max(0, offset)
        queryset = Tournament.objects.filter(visibility=Tournament.Visibility.PUBLIC).exclude(
            status=Tournament.Status.DRAFT
        )
        ordered = queryset.order_by("-starts_at", "id")
        return Response(
            {
                "count": queryset.count(),
                "results": [
                    {
                        "id": str(item.pk),
                        "title": item.title,
                        "status": item.status,
                        "startsAt": item.starts_at,
                        "endsAt": item.ends_at,
                    }
                    for item in ordered[offset : offset + limit]
                ],
            }
        )


class PublicBracketView(PublicReadView):
    def get(self, request, tournament_id):
        self.assert_public(request, tournament_id)
        tournament = get_object_or_404(Tournament, pk=tournament_id)
        matches = list(bracket_match_queryset().filter(tournament_id=tournament.pk))
        if not matches:
            raise NotFound("Сетка турнира ещё не создана.")
        first_round = [match for match in matches if match.round_index == 0]
        return Response(
            {
                "tournamentId": str(tournament.pk),
                "title": tournament.title,
                "bracketSize": max(2, len(first_round) * 2),
                "matches": [self._match(match) for match in matches],
            }
        )

    @staticmethod
    def _match(match: Match) -> dict:
        slots = sorted(match.slots.all(), key=lambda slot: slot.slot_index)
        names = [slot.participant.user.display_name if slot.participant_id else None for slot in slots]
        while len(names) < 2:
            names.append(None)
        winner = match.winner.user.display_name if match.winner_id else None
        return {
            "id": str(match.pk),
            "key": match.bracket_key,
            "roundIndex": match.round_index,
            "position": match.position,
            "status": "BYE" if match.kind == Match.Kind.BYE else match.status,
            "slots": [{"displayName": names[0]}, {"displayName": names[1]}],
            "winnerName": winner,
        }


def _sse(event_id: int | None, event: str, data: object) -> bytes:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}")
    return ("\n".join(lines) + "\n\n").encode("utf-8")


class _StreamSlot:
    """One open-stream reservation, released exactly once (stream end or response close)."""

    def __init__(self) -> None:
        global _open_streams
        with _stream_slots_lock:
            if _open_streams >= _setting("PUBLIC_SSE_MAX_STREAMS", 100):
                raise StreamCapacityExceeded()
            _open_streams += 1
        self._released = False

    def release(self) -> None:
        global _open_streams
        with _stream_slots_lock:
            if self._released:
                return
            self._released = True
            _open_streams = max(0, _open_streams - 1)


class _SlotStreamingResponse(StreamingHttpResponse):
    """Frees the slot even when the client leaves before the generator ever started."""

    def __init__(self, *args, slot: _StreamSlot, **kwargs):
        super().__init__(*args, **kwargs)
        self._slot = slot

    def close(self):
        try:
            super().close()
        finally:
            self._slot.release()


def _event_stream(match_id, tournament_id, after_event_id: int, slot: _StreamSlot):
    """Yield bounded SSE frames; the browser reconnects with Last-Event-ID when it ends."""
    poll = float(_setting("PUBLIC_SSE_POLL_SECONDS", 1.0))
    heartbeat = float(_setting("PUBLIC_SSE_HEARTBEAT_SECONDS", 15.0))
    max_seconds = float(_setting("PUBLIC_SSE_MAX_SECONDS", 55.0))
    started = last_beat = time.monotonic()
    cursor = after_event_id
    try:
        yield b"retry: 3000\n\n"
        # A cursor ahead of the durable log means the client holds state from another database.
        if cursor > current_event_cursor(tournament_id=tournament_id):
            yield _sse(None, "stream.resync_required", {"type": "stream.resync_required"})
            return
        while time.monotonic() - started < max_seconds:
            try:
                events = read_match_events_after(match_id=match_id, after_event_id=cursor, limit=50)
            except PublicEventInputError:
                yield _sse(None, "stream.resync_required", {"type": "stream.resync_required"})
                return
            for event in events:
                cursor = event["eventId"]
                yield _sse(cursor, event["type"], event)
                last_beat = time.monotonic()
            if not events and time.monotonic() - last_beat >= heartbeat:
                yield b": heartbeat\n\n"
                last_beat = time.monotonic()
            time.sleep(poll)
    finally:
        slot.release()


class PublicMatchEventsView(PublicReadView):
    def perform_content_negotiation(self, request, force=False):
        # Browsers open EventSource with `Accept: text/event-stream`, which no DRF renderer offers;
        # the stream bypasses renderers, but errors still use the default JSON renderer.
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get(self, request, match_id):
        match = get_object_or_404(Match.objects.only("id", "tournament_id"), pk=match_id)
        self.assert_public(request, match.tournament_id)
        raw = request.headers.get("Last-Event-ID") or request.query_params.get("lastEventId") or "0"
        try:
            after = int(raw)
        except ValueError:
            after = -1
        if after < 0:
            raise NotFound("Курсор события недействителен.")
        slot = _StreamSlot()
        response = _SlotStreamingResponse(
            _event_stream(match.pk, match.tournament_id, after, slot),
            content_type="text/event-stream; charset=utf-8",
            slot=slot,
        )
        response["Cache-Control"] = "no-store"
        response["X-Accel-Buffering"] = "no"
        response["Referrer-Policy"] = "no-referrer"
        return response

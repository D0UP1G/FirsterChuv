"""Event append and bounded cursor reads for the public match stream."""

from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.db.models import Max

from backend.apps.events.models import MatchEvent, MatchSnapshot
from backend.apps.events.public_payloads import (
    PublicEventInputError,
    validate_score_changed_payload,
)


MAX_EVENT_BATCH_SIZE = 250


def _scope_uuid(value: object, *, name: str) -> UUID:
    if not isinstance(value, (str, UUID)):
        raise PublicEventInputError(f"{name} must be a UUID")
    try:
        return UUID(str(value))
    except (ValueError, AttributeError) as error:
        raise PublicEventInputError(f"{name} must be a UUID") from error


def _serialize_event(event: MatchEvent) -> dict:
    if event.event_type != MatchEvent.Types.SCORE_CHANGED:
        raise PublicEventInputError("stored event type has no public serializer")
    return {
        "eventId": event.pk,
        "type": event.event_type,
        "matchId": str(event.match_id),
        "runId": str(event.run_id),
        "payload": validate_score_changed_payload(event.payload),
    }


@transaction.atomic
def append_event(
    *,
    tournament_id: UUID | str,
    match_id: UUID | str,
    run_id: UUID | str,
    event_type: str,
    public_payload: object,
) -> int:
    """Append an allowlisted event and return its monotonic global ID.

    Call from the domain transition's transaction when state and event must
    commit together. The nested atomic block remains part of that transaction.
    This slice supports only the concrete ``score.changed`` v1 payload; other
    documented event types need their own typed payload contract before writes.
    """
    if event_type != MatchEvent.Types.SCORE_CHANGED:
        raise PublicEventInputError("event type is not supported by this store slice")
    event = MatchEvent.objects.create(
        tournament_id=_scope_uuid(tournament_id, name="tournament_id"),
        match_id=_scope_uuid(match_id, name="match_id"),
        run_id=_scope_uuid(run_id, name="run_id"),
        event_type=MatchEvent.Types.SCORE_CHANGED,
        payload=validate_score_changed_payload(public_payload),
    )
    return event.pk


def read_events_after(
    *,
    tournament_id: UUID | str,
    after_event_id: int = 0,
    limit: int = 100,
) -> list[dict]:
    """Read one bounded tournament event page in durable ID order.

    Public access authorization is the caller's responsibility until the
    PublicAccessV1 HTTP/SSE adapter is implemented.
    """
    tournament_uuid = _scope_uuid(tournament_id, name="tournament_id")
    if type(after_event_id) is not int or after_event_id < 0:
        raise PublicEventInputError("after_event_id must be a non-negative integer")
    if type(limit) is not int or not 1 <= limit <= MAX_EVENT_BATCH_SIZE:
        raise PublicEventInputError(f"limit must be between 1 and {MAX_EVENT_BATCH_SIZE}")

    events = MatchEvent.objects.filter(
        tournament_id=tournament_uuid,
        id__gt=after_event_id,
    ).order_by("id")[:limit]
    return [_serialize_event(event) for event in events]


def current_event_cursor(*, tournament_id: UUID | str) -> int:
    """Return the latest event ID for a tournament, or zero when empty."""
    tournament_uuid = _scope_uuid(tournament_id, name="tournament_id")
    cursor = MatchEvent.objects.filter(tournament_id=tournament_uuid).aggregate(
        latest=Max("id")
    )["latest"]
    return cursor or 0


@transaction.atomic
def save_snapshot(*, match_id: UUID | str, run_id: UUID | str, last_event_id: int, public_payload: object) -> bool:
    """Persist a public snapshot only when its cursor is not stale."""
    match_uuid = _scope_uuid(match_id, name="match_id")
    run_uuid = _scope_uuid(run_id, name="run_id")
    if type(last_event_id) is not int or last_event_id < 0:
        raise PublicEventInputError("last_event_id must be a non-negative integer")
    payload = validate_score_changed_payload(public_payload)
    snapshot = MatchSnapshot.objects.select_for_update().filter(match_id=match_uuid).first()
    if snapshot is not None and snapshot.last_event_id > last_event_id:
        return False
    if snapshot is None:
        MatchSnapshot.objects.create(match_id=match_uuid, run_id=run_uuid, last_event_id=last_event_id, payload=payload)
    else:
        snapshot.run_id = run_uuid
        snapshot.last_event_id = last_event_id
        snapshot.payload = payload
        snapshot.save(update_fields=("run_id", "last_event_id", "payload", "updated_at"))
    return True


def read_snapshot(*, match_id: UUID | str) -> dict | None:
    match_uuid = _scope_uuid(match_id, name="match_id")
    snapshot = MatchSnapshot.objects.filter(match_id=match_uuid).first()
    if snapshot is None:
        return None
    return {"matchId": str(snapshot.match_id), "runId": str(snapshot.run_id), "lastEventId": snapshot.last_event_id, "payload": validate_score_changed_payload(snapshot.payload)}

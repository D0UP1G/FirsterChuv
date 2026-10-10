"""Event append and bounded cursor reads for the public match stream."""

from __future__ import annotations

import sqlite3
import time
from uuid import UUID

from django.db import OperationalError, connection, transaction
from django.db.models import F, Max

from backend.apps.events.models import MatchEvent, MatchSnapshot
from backend.apps.events.public_payloads import (
    PublicEventInputError,
    validate_score_changed_payload,
)


MAX_EVENT_BATCH_SIZE = 250
SNAPSHOT_WRITE_ATTEMPTS = 3


class PublicSnapshotConflict(RuntimeError):
    """One event cursor cannot describe two different public snapshots."""

    status_code = 409
    code = "public_snapshot_conflict"


class PublicSnapshotBusy(RuntimeError):
    """SQLite stayed busy after the bounded snapshot write retries."""

    status_code = 503
    code = "public_snapshot_busy"


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


def _is_sqlite_lock_error(error: OperationalError) -> bool:
    if connection.vendor != "sqlite":
        return False
    current: BaseException | None = error
    saw_sqlite_error_code = False
    while current is not None:
        code = getattr(current, "sqlite_errorcode", None)
        if isinstance(code, int):
            saw_sqlite_error_code = True
            if (code & 0xFF) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                return True
        current = current.__cause__ or current.__context__
    if saw_sqlite_error_code:
        return False
    message = " ".join(str(error).lower().split())
    return (
        message in {"database is locked", "database table is locked", "database schema is locked"}
        or message.startswith("database table is locked: ")
        or message.startswith("database schema is locked: ")
    )


def _save_snapshot_once(*, match_uuid: UUID, run_uuid: UUID, last_event_id: int, payload: dict) -> bool:
    # SQLite ignores SELECT FOR UPDATE. Start with a write statement so this
    # transaction owns the writer reservation before it reads the current row.
    # The no-op update also reserves the writer when the row does not exist.
    MatchSnapshot.objects.filter(pk=match_uuid).update(last_event_id=F("last_event_id"))

    snapshot = MatchSnapshot.objects.filter(pk=match_uuid).first()
    if snapshot is None:
        MatchSnapshot.objects.create(
            match_id=match_uuid,
            run_id=run_uuid,
            last_event_id=last_event_id,
            payload=payload,
        )
        return True

    if snapshot.last_event_id > last_event_id:
        return False
    if snapshot.last_event_id == last_event_id:
        if snapshot.run_id != run_uuid or snapshot.payload != payload:
            raise PublicSnapshotConflict(
                "Существующий курсор уже связан с другим снимком матча."
            )
        return True

    snapshot.run_id = run_uuid
    snapshot.last_event_id = last_event_id
    snapshot.payload = payload
    snapshot.save(update_fields=("run_id", "last_event_id", "payload", "updated_at"))
    return True


def save_snapshot(
    *, match_id: UUID | str, run_id: UUID | str, last_event_id: int, public_payload: object
) -> bool:
    """Persist a validated snapshot with write-first SQLite serialization.

    Returns False only for an older cursor. An exact retry at the current
    cursor is an idempotent success; conflicting state at that cursor is an
    error. If a caller already owns an outer transaction, it must retry that
    entire transaction when PublicSnapshotBusy is raised.
    """
    match_uuid = _scope_uuid(match_id, name="match_id")
    run_uuid = _scope_uuid(run_id, name="run_id")
    if type(last_event_id) is not int or last_event_id < 0:
        raise PublicEventInputError("last_event_id must be a non-negative integer")
    payload = validate_score_changed_payload(public_payload)

    if connection.in_atomic_block:
        try:
            with transaction.atomic():
                return _save_snapshot_once(
                    match_uuid=match_uuid,
                    run_uuid=run_uuid,
                    last_event_id=last_event_id,
                    payload=payload,
                )
        except OperationalError as error:
            if not _is_sqlite_lock_error(error):
                raise
            raise PublicSnapshotBusy(
                "База занята; повторите сохранение публичного снимка позже."
            ) from error

    for attempt in range(SNAPSHOT_WRITE_ATTEMPTS):
        try:
            with transaction.atomic():
                return _save_snapshot_once(
                    match_uuid=match_uuid,
                    run_uuid=run_uuid,
                    last_event_id=last_event_id,
                    payload=payload,
                )
        except OperationalError as error:
            if not _is_sqlite_lock_error(error):
                raise
            if attempt == SNAPSHOT_WRITE_ATTEMPTS - 1:
                raise PublicSnapshotBusy(
                    "База занята; повторите сохранение публичного снимка позже."
                ) from error
            time.sleep(0.01 * (attempt + 1))
    raise AssertionError("bounded snapshot retry loop exited unexpectedly")


def read_snapshot(*, match_id: UUID | str) -> dict | None:
    match_uuid = _scope_uuid(match_id, name="match_id")
    snapshot = MatchSnapshot.objects.filter(match_id=match_uuid).first()
    if snapshot is None:
        return None
    return {
        "matchId": str(snapshot.match_id),
        "runId": str(snapshot.run_id),
        "lastEventId": snapshot.last_event_id,
        "payload": validate_score_changed_payload(snapshot.payload),
    }

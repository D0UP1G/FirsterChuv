"""Transactional, body-bound idempotency for match API commands."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from django.db import OperationalError, models, transaction

from backend.apps.competition.models import Match, MatchCommandReceipt
from backend.apps.competition.runtime import (
    MatchRuntimeBusy,
    _is_sqlite_lock_error,
)


class MatchCommandInputError(ValueError):
    """A command key or command payload is invalid."""


class MatchCommandIdempotencyConflict(RuntimeError):
    """A scoped command key was reused for a different actor intent."""

    status_code = 409
    code = "idempotency_conflict"


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _key_digest(key: str) -> str:
    if not isinstance(key, str):
        raise MatchCommandInputError("Idempotency-Key is required.")
    try:
        encoded = key.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise MatchCommandInputError("Idempotency-Key is invalid.") from error
    if (
        not encoded
        or len(encoded) > 128
        or not key.strip()
        or any(byte < 0x20 or byte == 0x7F for byte in encoded)
    ):
        raise MatchCommandInputError(
            "Idempotency-Key must contain 1 to 128 printable UTF-8 bytes."
        )
    return _digest(encoded)


def _request_digest(action: str, body: Mapping[str, object]) -> str:
    if not isinstance(action, str) or not action.strip() or len(action) > 32:
        raise MatchCommandInputError("Unknown match command action.")
    if not isinstance(body, Mapping):
        raise MatchCommandInputError("Command body must be a JSON object.")
    canonical = json.dumps(
        {"action": action, "body": body},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return _digest(canonical)


def _reserve_match(match_id: UUID | str) -> None:
    """Take a SQLite writer reservation before inspecting receipt/state rows."""
    changed = Match.objects.filter(pk=match_id).update(
        updated_at=models.F("updated_at")
    )
    if not changed:
        raise Match.DoesNotExist


def _find_replay(
    *,
    match_id: UUID | str,
    actor_id: UUID | str,
    action: str,
    key_digest: str,
    request_digest: str,
) -> dict | None:
    receipt = MatchCommandReceipt.objects.filter(
        match_id=match_id,
        actor_id=actor_id,
        idempotency_sha256=key_digest,
    ).first()
    if receipt is None:
        return None
    if receipt.action != action or receipt.request_sha256 != request_digest:
        raise MatchCommandIdempotencyConflict(
            "Idempotency-Key was already used for another match command."
        )
    return json.loads(json.dumps(receipt.response_payload, ensure_ascii=False))


def _replay_before_prepare(
    *,
    match_id: UUID | str,
    actor_id: UUID | str,
    action: str,
    key_digest: str,
    request_digest: str,
    authorize: Callable[[], None] | None,
) -> dict | None:
    """Avoid external catalog reads for an exact retry, while keeping SQLite safe."""
    with transaction.atomic():
        _reserve_match(match_id)
        if authorize is not None:
            authorize()
        return _find_replay(
            match_id=match_id,
            actor_id=actor_id,
            action=action,
            key_digest=key_digest,
            request_digest=request_digest,
        )


def execute_match_command(
    *,
    match_id: UUID | str,
    actor_id: UUID | str,
    action: str,
    idempotency_key: str,
    body: Mapping[str, object],
    perform: Callable[[Any], Mapping[str, object]],
    prepare: Callable[[], Any] | None = None,
    authorize: Callable[[], None] | None = None,
) -> dict:
    """Apply a command and persist its exact response in the same transaction.

    ``prepare`` is for read-only external/catalog work. It runs outside the
    effect transaction and is skipped for an already-recorded exact retry.
    The receipt is rechecked after acquiring the write reservation.
    """
    try:
        match_uuid = match_id if isinstance(match_id, UUID) else UUID(str(match_id))
        actor_uuid = actor_id if isinstance(actor_id, UUID) else UUID(str(actor_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise MatchCommandInputError("Match and actor IDs must be UUIDs.") from error

    key_digest = _key_digest(idempotency_key)
    request_digest = _request_digest(action, body)
    for attempt in range(3):
        try:
            if prepare is not None:
                replay = _replay_before_prepare(
                    match_id=match_uuid,
                    actor_id=actor_uuid,
                    action=action,
                    key_digest=key_digest,
                    request_digest=request_digest,
                    authorize=authorize,
                )
                if replay is not None:
                    return replay
                prepared = prepare()
            else:
                prepared = None

            with transaction.atomic():
                _reserve_match(match_uuid)
                if authorize is not None:
                    authorize()
                replay = _find_replay(
                    match_id=match_uuid,
                    actor_id=actor_uuid,
                    action=action,
                    key_digest=key_digest,
                    request_digest=request_digest,
                )
                if replay is not None:
                    return replay

                result = perform(prepared)
                if not isinstance(result, Mapping):
                    raise TypeError("match command must return a response object")
                response_payload = json.loads(
                    json.dumps(dict(result), ensure_ascii=False)
                )
                run_id = response_payload.get("runId")
                MatchCommandReceipt.objects.create(
                    match_id=match_uuid,
                    actor_id=actor_uuid,
                    run_id=run_id,
                    action=action,
                    idempotency_sha256=key_digest,
                    request_sha256=request_digest,
                    response_payload=response_payload,
                )
                return response_payload
        except MatchRuntimeBusy:
            if attempt == 2:
                raise
        except OperationalError as error:
            if not _is_sqlite_lock_error(error):
                raise
            if attempt == 2:
                raise MatchRuntimeBusy(
                    "match storage is busy; retry the request"
                ) from error
        if attempt < 2:
            time.sleep(0.01 * (attempt + 1))
    raise MatchRuntimeBusy("match storage is busy; retry the request")

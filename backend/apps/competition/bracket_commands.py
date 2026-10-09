"""Transactional idempotency receipts for bracket administration commands."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from uuid import UUID

from django.db import models, transaction

from backend.apps.competition.models import BracketCommandReceipt
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.services import (
    EDITABLE_TOURNAMENT_STATUSES,
    retry_sqlite_locked_write,
)
from backend.apps.competition.services import BracketLifecycleConflict


class BracketCommandInputError(ValueError):
    """Raised when an idempotency key is missing or malformed."""


class BracketCommandIdempotencyConflict(RuntimeError):
    """Raised when a key has already been recorded for another intent."""

    status_code = 409
    code = "idempotency_conflict"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _idempotency_digest(key: str) -> str:
    if not isinstance(key, str):
        raise BracketCommandInputError("Idempotency-Key is required.")
    try:
        encoded = key.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise BracketCommandInputError("Idempotency-Key is invalid.") from error
    if (
        not encoded
        or len(encoded) > 128
        or not key.strip()
        or any(byte < 0x20 or byte == 0x7F for byte in encoded)
    ):
        raise BracketCommandInputError(
            "Idempotency-Key must contain 1 to 128 printable UTF-8 bytes."
        )
    return _sha256(encoded)


def _intent_digest(
    *,
    tournament_id: UUID | str,
    actor_id: UUID | str,
    action: str,
    reason: str,
    arguments: Mapping[str, object],
) -> str:
    canonical = json.dumps(
        {
            "tournamentId": str(tournament_id),
            "actorId": str(actor_id),
            "action": action,
            "reason": reason,
            "arguments": arguments,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return _sha256(canonical)


@retry_sqlite_locked_write
@transaction.atomic
def execute_bracket_command(
    *,
    tournament_id: UUID | str,
    actor_id: UUID | str,
    action: str,
    idempotency_key: str,
    reason: str,
    arguments: Mapping[str, object],
    perform: Callable[[], Mapping[str, object]],
) -> dict:
    """Run a bracket write and its response receipt in one short transaction.

    A conditional tournament update is the first SQL statement. This serializes
    new commands with lifecycle changes on SQLite before roster or bracket reads.
    Exact retries replay their original response, including after the tournament
    is no longer editable; a new/different command still observes the lifecycle
    guard and cannot change it.
    """
    if not isinstance(action, str) or action not in BracketCommandReceipt.Action.values:
        raise BracketCommandInputError("Unknown bracket command action.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise BracketCommandInputError("reason must contain 1 to 500 characters.")
    if not isinstance(arguments, Mapping):
        raise BracketCommandInputError("command arguments must be an object.")
    if not callable(perform):
        raise BracketCommandInputError("command operation is required.")
    try:
        tournament_uuid = (
            tournament_id if isinstance(tournament_id, UUID) else UUID(str(tournament_id))
        )
        actor_uuid = actor_id if isinstance(actor_id, UUID) else UUID(str(actor_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise BracketCommandInputError("Tournament and actor IDs must be UUIDs.") from error
    key_digest = _idempotency_digest(idempotency_key)
    request_digest = _intent_digest(
        tournament_id=tournament_uuid,
        actor_id=actor_uuid,
        action=action,
        reason=reason,
        arguments=arguments,
    )

    # Keep this as the first database statement in the command transaction.
    editable = Tournament.objects.filter(
        pk=tournament_uuid,
        status__in=EDITABLE_TOURNAMENT_STATUSES,
    ).update(updated_at=models.F("updated_at"))

    receipt = BracketCommandReceipt.objects.filter(
        tournament_id=tournament_uuid,
        idempotency_sha256=key_digest,
    ).first()
    if receipt is not None:
        if (
            receipt.actor_id != actor_uuid
            or receipt.action != action
            or receipt.request_sha256 != request_digest
        ):
            raise BracketCommandIdempotencyConflict(
                "Idempotency-Key was already used for another bracket command."
            )
        # JSONField already returned a detached value; copy through JSON to keep
        # response objects from sharing nested mutable containers with the model.
        return json.loads(json.dumps(receipt.response_payload, ensure_ascii=False))

    if editable == 0:
        if not Tournament.objects.filter(pk=tournament_uuid).exists():
            raise Tournament.DoesNotExist("Турнир не найден.")
        raise BracketLifecycleConflict(
            "Сетку можно создавать и изменять только у чернового или запланированного турнира."
        )

    result = perform()
    if not isinstance(result, Mapping):
        raise TypeError("bracket command must return a response object")
    response_payload = json.loads(json.dumps(dict(result), ensure_ascii=False))
    BracketCommandReceipt.objects.create(
        tournament_id=tournament_uuid,
        actor_id=actor_uuid,
        action=action,
        idempotency_sha256=key_digest,
        request_sha256=request_digest,
        reason=reason,
        response_payload=response_payload,
    )
    return response_payload

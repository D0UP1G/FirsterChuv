"""Transactional persistence for pause, resume, and duration extension commands."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.competition.domain.admin_actions import (
    AdminAction,
    AdminActor,
    AdminCommand,
    MatchAdminSnapshot,
    RunStatus,
    plan_extension,
    plan_pause,
    plan_resume,
)
from backend.apps.competition.domain.clock import (
    ClockSnapshot,
    pause_clock,
    resume_clock,
)
from backend.apps.competition.models import (
    Match,
    MatchAdminCommandReceipt,
    MatchRun,
    MatchSlot,
)


MAX_EXTENSION_SECONDS = 600


class AdminCommandPersistenceError(RuntimeError):
    """A match admin command is unauthorized, conflicting, or no longer valid."""

    status_code = 409
    code = "admin_command_conflict"


def _fingerprint(*, actor_id: UUID, action: AdminAction, reason: str | None, seconds: int | None) -> str:
    intent = {
        "actorId": str(actor_id),
        "action": action.value,
        "reason": reason,
        "seconds": seconds,
    }
    canonical = json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _clock(run: MatchRun) -> ClockSnapshot:
    return ClockSnapshot(
        status=run.status,
        allowed_duration_ms=run.allowed_duration_ms,
        started_at=run.started_at,
        paused_at=run.paused_at,
        accumulated_pause_ms=run.accumulated_pause_ms,
    )


def _replay(previous: MatchAdminCommandReceipt, *, actor_id: UUID, fingerprint: str) -> dict:
    if previous.request_sha256 != fingerprint or previous.actor_id != actor_id:
        raise AdminCommandPersistenceError("command_id was reused with different intent")
    return previous.response_payload


@transaction.atomic
def execute_match_admin_command(
    *,
    actor_user_id: UUID | str,
    match_id: UUID | str,
    command_id: str,
    action: AdminAction | str,
    reason: str | None = None,
    seconds: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Apply a command and its durable replay receipt in one transaction."""
    try:
        normalized_action = AdminAction(action)
    except (TypeError, ValueError) as error:
        raise AdminCommandPersistenceError("unsupported match admin action") from error
    if normalized_action not in (AdminAction.PAUSE, AdminAction.RESUME, AdminAction.EXTEND):
        raise AdminCommandPersistenceError("this command is outside the persisted clock-actions slice")
    if not isinstance(command_id, str) or not command_id.strip() or len(command_id) > 128:
        raise AdminCommandPersistenceError("command_id must be non-empty and at most 128 characters")
    try:
        actor_id = UUID(str(actor_user_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise AdminCommandPersistenceError("actor user ID must be a UUID") from error

    try:
        actor_record = User.objects.get(pk=actor_id)
    except User.DoesNotExist as error:
        raise AdminCommandPersistenceError("active admin actor was not found") from error
    if not actor_record.is_active or actor_record.role != User.Roles.ADMIN:
        raise AdminCommandPersistenceError("match actions require an active admin")
    actor = AdminActor(user_id=actor_record.pk, role=actor_record.role, is_active=actor_record.is_active)
    command = AdminCommand(actor=actor, command_id=command_id, reason=reason)
    fingerprint = _fingerprint(
        actor_id=actor_id,
        action=normalized_action,
        reason=reason,
        seconds=seconds if normalized_action is AdminAction.EXTEND else None,
    )

    previous = MatchAdminCommandReceipt.objects.filter(match_id=match_id, command_id=command_id).first()
    if previous is not None:
        return _replay(previous, actor_id=actor_id, fingerprint=fingerprint)

    match_state = Match.objects.filter(pk=match_id).values("current_run_id").first()
    if match_state is None:
        raise AdminCommandPersistenceError("match was not found")
    current_run_id = match_state["current_run_id"]
    if current_run_id is None:
        raise AdminCommandPersistenceError("match has no current run")
    # Run → match is the shared write-lock order used by readiness and ledger services.
    locked_run = MatchRun.objects.filter(pk=current_run_id).update(revision=models.F("revision"))
    if not locked_run:
        raise AdminCommandPersistenceError("current match run was not found")
    changed = Match.objects.filter(pk=match_id).update(updated_at=models.F("updated_at"))
    if not changed:
        raise AdminCommandPersistenceError("match was not found")
    match = Match.objects.get(pk=match_id)
    if match.current_run_id != current_run_id:
        raise AdminCommandPersistenceError("current match run changed concurrently")
    previous = MatchAdminCommandReceipt.objects.filter(match=match, command_id=command_id).first()
    if previous is not None:
        return _replay(previous, actor_id=actor_id, fingerprint=fingerprint)

    run = MatchRun.objects.get(pk=current_run_id)
    participant_ids = tuple(
        MatchSlot.objects.filter(match=match, resolution=MatchSlot.Resolution.PLAYER)
        .order_by("slot_index")
        .values_list("participant__user_id", flat=True)
    )
    participants = (*participant_ids, *([None] * (2 - len(participant_ids))))[:2]
    snapshot = MatchAdminSnapshot(
        match_id=match.pk,
        run_id=run.pk,
        run_status=run.status,
        participant_user_ids=participants,
        downstream_started=False,
    )
    try:
        if normalized_action is AdminAction.PAUSE:
            plan = plan_pause(snapshot, command)
            updated_clock = pause_clock(_clock(run), now or timezone.now())
        elif normalized_action is AdminAction.RESUME:
            plan = plan_resume(snapshot, command)
            updated_clock = resume_clock(_clock(run), now or timezone.now())
        else:
            plan = plan_extension(
                snapshot,
                command,
                seconds=seconds,
                max_extension_seconds=MAX_EXTENSION_SECONDS,
            )
            updated_clock = _clock(run)
    except (TypeError, ValueError) as error:
        raise AdminCommandPersistenceError(str(error)) from error

    if normalized_action is AdminAction.PAUSE:
        run.status = updated_clock.status.value
        run.paused_at = updated_clock.paused_at
    elif normalized_action is AdminAction.RESUME:
        run.status = updated_clock.status.value
        run.paused_at = None
        run.accumulated_pause_ms = updated_clock.accumulated_pause_ms
    else:
        run.allowed_duration_ms += seconds * 1000
    run.revision += 1
    run.save(update_fields=(
        "status", "paused_at", "accumulated_pause_ms", "allowed_duration_ms", "revision"
    ))
    match.status = run.status
    match.save(update_fields=("status", "updated_at"))
    response = {
        "matchId": str(match.pk),
        "runId": str(run.pk),
        "commandId": command_id,
        "action": normalized_action.value,
        "status": run.status,
        "revision": run.revision,
        "allowedDurationMs": run.allowed_duration_ms,
        "pausedAt": run.paused_at.isoformat() if run.paused_at else None,
        "accumulatedPauseMs": run.accumulated_pause_ms,
        "reason": reason,
    }
    try:
        with transaction.atomic():
            MatchAdminCommandReceipt.objects.create(
                match=match,
                actor=actor_record,
                run=run,
                command_id=command_id,
                action=normalized_action.value,
                request_sha256=fingerprint,
                reason=reason or "",
                response_payload=response,
            )
    except IntegrityError as error:
        raise AdminCommandPersistenceError("command_id was concurrently claimed") from error
    return response

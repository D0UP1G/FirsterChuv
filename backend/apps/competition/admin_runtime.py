"""Transactional persistence for pause, resume, and duration extension commands."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, models, transaction
from django.db.models import Q
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
    plan_rematch,
    plan_technical_result,
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


def _fingerprint(
    *, actor_id: UUID, action: AdminAction, reason: str | None,
    seconds: int | None, winner_user_id: UUID | str | None,
) -> str:
    intent = {
        "actorId": str(actor_id),
        "action": action.value,
        "reason": reason,
        "seconds": seconds,
        "winnerUserId": str(winner_user_id) if winner_user_id is not None else None,
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
    winner_user_id: UUID | str | None = None,
    now: datetime | None = None,
) -> dict:
    """Apply a command and its durable replay receipt in one transaction."""
    try:
        normalized_action = AdminAction(action)
    except (TypeError, ValueError) as error:
        raise AdminCommandPersistenceError("unsupported match admin action") from error
    if normalized_action not in (
        AdminAction.PAUSE,
        AdminAction.RESUME,
        AdminAction.EXTEND,
        AdminAction.TECHNICAL_RESULT,
        AdminAction.REMATCH,
    ):
        raise AdminCommandPersistenceError("this command is outside the persisted admin-actions slice")
    if not isinstance(command_id, str) or not command_id.strip() or len(command_id) > 128:
        raise AdminCommandPersistenceError("command_id must be non-empty and at most 128 characters")
    if normalized_action is AdminAction.EXTEND:
        if winner_user_id is not None:
            raise AdminCommandPersistenceError("extend does not accept a winner")
    elif seconds is not None:
        raise AdminCommandPersistenceError("seconds are accepted only by extend")
    if normalized_action is AdminAction.TECHNICAL_RESULT:
        if winner_user_id is None:
            raise AdminCommandPersistenceError("technical result requires a winner")
    elif winner_user_id is not None:
        raise AdminCommandPersistenceError("winner is accepted only by technical_result")
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
        winner_user_id=winner_user_id if normalized_action is AdminAction.TECHNICAL_RESULT else None,
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
    receipt_run_id = run.pk
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
        downstream_started=_downstream_started(match),
    )
    try:
        if normalized_action is AdminAction.PAUSE:
            plan = plan_pause(snapshot, command)
            updated_clock = pause_clock(_clock(run), now or timezone.now())
        elif normalized_action is AdminAction.RESUME:
            plan = plan_resume(snapshot, command)
            updated_clock = resume_clock(_clock(run), now or timezone.now())
        elif normalized_action is AdminAction.EXTEND:
            plan = plan_extension(
                snapshot,
                command,
                seconds=seconds,
                max_extension_seconds=MAX_EXTENSION_SECONDS,
            )
            updated_clock = _clock(run)
        elif normalized_action is AdminAction.TECHNICAL_RESULT:
            plan = plan_technical_result(
                snapshot,
                command,
                winner_user_id=winner_user_id,
            )
            updated_clock = _clock(run)
        else:
            plan = plan_rematch(snapshot, command)
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
    elif normalized_action is AdminAction.EXTEND:
        run.allowed_duration_ms += seconds * 1000
    elif normalized_action is AdminAction.TECHNICAL_RESULT:
        winner_entry = MatchSlot.objects.get(
            match=match,
            participant__user_id=plan.winner_user_id,
        ).participant
        run.status = MatchRun.Status.FINISHED
        run.finished_at = now or timezone.now()
        run.winner = winner_entry
        run.technical_reason = reason
        run.revision += 1
        run.save(update_fields=("status", "finished_at", "winner", "technical_reason", "revision"))
        match.status = Match.Status.FINISHED
        match.winner = winner_entry
        match.save(update_fields=("status", "winner", "updated_at"))
        _advance_winner(match, winner_entry)
    elif normalized_action is AdminAction.REMATCH:
        run.status = MatchRun.Status.SUPERSEDED
        run.revision += 1
        run.save(update_fields=("status", "revision"))
        replacement = MatchRun.objects.create(
            match=match,
            sequence=run.sequence + 1,
            status=MatchRun.Status.READY,
            allowed_duration_ms=run.allowed_duration_ms,
            score_rule=run.score_rule,
            scoring_version=run.scoring_version,
            start_mode=run.start_mode,
            problem_versions=run.problem_versions,
            score_snapshot={},
        )
        match.current_run = replacement
        match.status = Match.Status.READY
        match.winner = None
        match.save(update_fields=("current_run", "status", "winner", "updated_at"))
        run = replacement
    if normalized_action in (AdminAction.PAUSE, AdminAction.RESUME, AdminAction.EXTEND):
        run.revision += 1
        run.save(update_fields=(
            "status", "paused_at", "accumulated_pause_ms", "allowed_duration_ms", "revision"
        ))
        match.status = run.status
        match.save(update_fields=("status", "updated_at"))
    elif normalized_action not in (AdminAction.TECHNICAL_RESULT, AdminAction.REMATCH):  # defensive
        raise AdminCommandPersistenceError("unsupported match admin action")
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
        "winnerUserId": str(winner_user_id) if winner_user_id is not None else None,
    }
    try:
        with transaction.atomic():
            MatchAdminCommandReceipt.objects.create(
                match=match,
                actor=actor_record,
                run_id=receipt_run_id,
                command_id=command_id,
                action=normalized_action.value,
                request_sha256=fingerprint,
                reason=reason or "",
                response_payload=response,
            )
    except IntegrityError as error:
        raise AdminCommandPersistenceError("command_id was concurrently claimed") from error
    return response


def _downstream_started(match: Match) -> bool:
    if match.next_match_id is None:
        return False
    return Match.objects.filter(pk=match.next_match_id).filter(
        Q(current_run__started_at__isnull=False)
        | Q(status__in=(Match.Status.RUNNING, Match.Status.PAUSED, Match.Status.FINALIZING, Match.Status.FINISHED, Match.Status.TIED))
    ).exists()


def _advance_winner(match: Match, winner_entry) -> None:
    if match.next_match_id is None or match.next_slot is None:
        return
    updated = MatchSlot.objects.filter(
        match_id=match.next_match_id,
        slot_index=match.next_slot,
        upstream_match=match,
        resolution=MatchSlot.Resolution.WAITING,
        participant__isnull=True,
    ).update(
        participant=winner_entry,
        resolution=MatchSlot.Resolution.PLAYER,
    )
    if updated != 1:
        raise AdminCommandPersistenceError("downstream slot is no longer available for winner advancement")

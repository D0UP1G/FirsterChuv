"""Transactional persistence for pause, resume, and duration extension commands."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from functools import wraps
from uuid import UUID

from django.db import IntegrityError, OperationalError, connection, models, transaction
from django.db.models import Q
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.competition.domain.admin_actions import (
    AdminAction,
    AdminActor,
    AdminCommand,
    MatchAdminSnapshot,
    ReplacementParticipant,
    RunStatus,
    plan_extension,
    plan_pause,
    plan_resume,
    plan_rematch,
    plan_replacement,
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
    MatchRunReady,
    MatchSlot,
)
from backend.apps.tournaments.models import TournamentParticipant
from backend.apps.events.models import MatchEvent
from backend.apps.events.services import append_event


MAX_EXTENSION_SECONDS = 600


class AdminCommandPersistenceError(RuntimeError):
    """A match admin command is unauthorized, conflicting, or no longer valid."""

    status_code = 409
    code = "admin_command_conflict"


class AdminCommandPersistenceBusy(AdminCommandPersistenceError):
    """A short-lived SQLite write collision exhausted bounded retries."""

    status_code = 503
    code = "admin_command_busy"


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
        message == "database is locked"
        or message == "database table is locked"
        or message.startswith("database table is locked: ")
        or message == "database schema is locked"
        or message.startswith("database schema is locked: ")
    )


def _retry_sqlite_command(function):
    """Retry the whole atomic command after a transient SQLite lock."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        for attempt in range(3):
            try:
                with transaction.atomic():
                    return function(*args, **kwargs)
            except OperationalError as error:
                if not _is_sqlite_lock_error(error):
                    raise
                if attempt == 2:
                    raise AdminCommandPersistenceBusy(
                        "База занята; повторите действие позже."
                    ) from error
                time.sleep(0.01 * (attempt + 1))

    return wrapped


def _fingerprint(
    *, actor_id: UUID, action: AdminAction, reason: str | None,
    seconds: int | None, winner_user_id: UUID | str | None,
    old_user_id: UUID | str | None = None,
    replacement_user_id: UUID | str | None = None,
) -> str:
    intent = {
        "actorId": str(actor_id),
        "action": action.value,
        "reason": reason,
        "seconds": seconds,
        "winnerUserId": str(winner_user_id) if winner_user_id is not None else None,
        "oldUserId": str(old_user_id) if old_user_id is not None else None,
        "replacementUserId": str(replacement_user_id) if replacement_user_id is not None else None,
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


@_retry_sqlite_command
def execute_match_admin_command(
    *,
    actor_user_id: UUID | str,
    match_id: UUID | str,
    command_id: str,
    action: AdminAction | str,
    reason: str | None = None,
    seconds: int | None = None,
    winner_user_id: UUID | str | None = None,
    old_user_id: UUID | str | None = None,
    replacement_user_id: UUID | str | None = None,
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
        AdminAction.REPLACE_PARTICIPANT,
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
    if normalized_action is AdminAction.REPLACE_PARTICIPANT:
        if old_user_id is None or replacement_user_id is None:
            raise AdminCommandPersistenceError("participant replacement requires old and replacement user IDs")
    elif old_user_id is not None or replacement_user_id is not None:
        raise AdminCommandPersistenceError("participant IDs are accepted only by replace_participant")
    try:
        actor_id = UUID(str(actor_user_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise AdminCommandPersistenceError("actor user ID must be a UUID") from error

    fingerprint = _fingerprint(
        actor_id=actor_id,
        action=normalized_action,
        reason=reason,
        seconds=seconds if normalized_action is AdminAction.EXTEND else None,
        winner_user_id=winner_user_id if normalized_action is AdminAction.TECHNICAL_RESULT else None,
        old_user_id=old_user_id if normalized_action is AdminAction.REPLACE_PARTICIPANT else None,
        replacement_user_id=replacement_user_id if normalized_action is AdminAction.REPLACE_PARTICIPANT else None,
    )

    # Reserve a write before any database read. This serializes same-key retries
    # and avoids SQLite DEFERRED read-to-write upgrades across separate threads.
    changed = Match.objects.filter(pk=match_id).update(updated_at=models.F("updated_at"))
    if not changed:
        raise AdminCommandPersistenceError("match was not found")

    try:
        actor_record = User.objects.get(pk=actor_id)
    except User.DoesNotExist as error:
        raise AdminCommandPersistenceError("active admin actor was not found") from error
    if not actor_record.is_active or actor_record.role != User.Roles.ADMIN:
        raise AdminCommandPersistenceError("match actions require an active admin")
    actor = AdminActor(user_id=actor_record.pk, role=actor_record.role, is_active=actor_record.is_active)
    command = AdminCommand(actor=actor, command_id=command_id, reason=reason)

    match = Match.objects.get(pk=match_id)
    current_run_id = match.current_run_id
    if current_run_id is not None:
        locked_run = MatchRun.objects.filter(pk=current_run_id).update(revision=models.F("revision"))
        if not locked_run:
            raise AdminCommandPersistenceError("current match run was not found")
        match.refresh_from_db()
        if match.current_run_id != current_run_id:
            raise AdminCommandPersistenceError("current match run changed concurrently")

    previous = MatchAdminCommandReceipt.objects.filter(match=match, command_id=command_id).first()
    if previous is not None:
        return _replay(previous, actor_id=actor_id, fingerprint=fingerprint)

    run = MatchRun.objects.get(pk=current_run_id) if current_run_id is not None else None
    if run is None and normalized_action is not AdminAction.REPLACE_PARTICIPANT:
        raise AdminCommandPersistenceError("match has no current run")
    receipt_run_id = run.pk if run is not None else None
    participants_by_slot: list[UUID | None] = [None, None]
    for slot_index, user_id in MatchSlot.objects.filter(
        match=match,
        resolution=MatchSlot.Resolution.PLAYER,
    ).values_list("slot_index", "participant__user_id"):
        participants_by_slot[slot_index] = user_id
    snapshot = MatchAdminSnapshot(
        match_id=match.pk,
        run_id=run.pk if run is not None else None,
        run_status=run.status if run is not None else MatchRun.Status.WAITING,
        participant_user_ids=tuple(participants_by_slot),
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
        elif normalized_action is AdminAction.REMATCH:
            plan = plan_rematch(snapshot, command)
            updated_clock = _clock(run)
        else:
            try:
                old_id = UUID(str(old_user_id))
                replacement_id = UUID(str(replacement_user_id))
                replacement_record = User.objects.get(pk=replacement_id)
                replacement_snapshot = ReplacementParticipant(
                    user_id=replacement_record.pk,
                    role=replacement_record.role,
                    is_active=replacement_record.is_active,
                )
            except (TypeError, ValueError, AttributeError) as error:
                raise AdminCommandPersistenceError("participant IDs must be valid UUIDs") from error
            except User.DoesNotExist as error:
                raise AdminCommandPersistenceError("replacement participant was not found") from error
            plan = plan_replacement(
                snapshot,
                command,
                old_user_id=old_id,
                replacement=replacement_snapshot,
            )
            updated_clock = _clock(run) if run is not None else None
    except (TypeError, ValueError) as error:
        raise AdminCommandPersistenceError(str(error)) from error

    if normalized_action is AdminAction.REPLACE_PARTICIPANT:
        slot = MatchSlot.objects.select_for_update().get(
            match=match,
            slot_index=plan.slot_index,
            resolution=MatchSlot.Resolution.PLAYER,
            participant__user_id=plan.replaced_user_id,
        )
        tournament = match.tournament
        TournamentParticipant.objects.filter(
            tournament=tournament,
            user_id=plan.replaced_user_id,
            status=TournamentParticipant.Status.ACTIVE,
        ).update(status=TournamentParticipant.Status.REMOVED, removed_at=now or timezone.now())
        replacement_entry, _created = TournamentParticipant.objects.get_or_create(
            tournament=tournament,
            user_id=plan.replacement_user_id,
            defaults={"seed": None, "status": TournamentParticipant.Status.ACTIVE},
        )
        if replacement_entry.status != TournamentParticipant.Status.ACTIVE:
            replacement_entry.status = TournamentParticipant.Status.ACTIVE
            replacement_entry.removed_at = None
            replacement_entry.seed = None
            replacement_entry.save(update_fields=("status", "removed_at", "seed"))
        if MatchSlot.objects.filter(
            match__tournament=tournament,
            participant=replacement_entry,
        ).exclude(pk=slot.pk).exists():
            raise AdminCommandPersistenceError("replacement participant already occupies another match slot")
        slot.participant = replacement_entry
        slot.save(update_fields=("participant",))
        if run is not None:
            MatchRunReady.objects.filter(run=run, participant__user_id=plan.replaced_user_id).delete()
            participant_ids = list(run.participant_user_ids)
            if len(participant_ids) != 2:
                raise AdminCommandPersistenceError("current run has no frozen participant snapshot")
            participant_ids[plan.slot_index] = str(plan.replacement_user_id)
            if plan.new_run_required:
                run.status = MatchRun.Status.SUPERSEDED
                run.revision += 1
                run.save(update_fields=("status", "revision"))
                run = MatchRun.objects.create(
                    match=match,
                    sequence=run.sequence + 1,
                    status=MatchRun.Status.READY,
                    allowed_duration_ms=run.allowed_duration_ms,
                    score_rule=run.score_rule,
                    scoring_version=run.scoring_version,
                    start_mode=run.start_mode,
                    problem_versions=run.problem_versions,
                    participant_user_ids=participant_ids,
                    score_snapshot={},
                )
                match.current_run = run
                match.status = Match.Status.READY
                match.save(update_fields=("current_run", "status", "updated_at"))
            else:
                run.participant_user_ids = participant_ids
                run.revision += 1
                run.save(update_fields=("participant_user_ids", "revision"))
    elif normalized_action is AdminAction.PAUSE:
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
        _reopen_unstarted_downstream(match)
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
            participant_user_ids=run.participant_user_ids,
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
    elif normalized_action not in (
        AdminAction.TECHNICAL_RESULT,
        AdminAction.REMATCH,
        AdminAction.REPLACE_PARTICIPANT,
    ):  # defensive
        raise AdminCommandPersistenceError("unsupported match admin action")
    response = {
        "matchId": str(match.pk),
        "runId": str(run.pk) if run is not None else None,
        "commandId": command_id,
        "action": normalized_action.value,
        "status": run.status if run is not None else MatchRun.Status.WAITING,
        "revision": run.revision if run is not None else 0,
        "allowedDurationMs": run.allowed_duration_ms if run is not None else None,
        "pausedAt": run.paused_at.isoformat() if run is not None and run.paused_at else None,
        "accumulatedPauseMs": run.accumulated_pause_ms if run is not None else 0,
        "reason": reason,
        "winnerUserId": str(winner_user_id) if winner_user_id is not None else None,
        "replacedUserId": str(old_user_id) if old_user_id is not None else None,
        "replacementUserId": str(replacement_user_id) if replacement_user_id is not None else None,
    }
    if run is not None:
        append_event(
            tournament_id=match.tournament_id,
            match_id=match.pk,
            run_id=run.pk,
            event_type=MatchEvent.Types.ADMIN_ACTION,
            public_payload={
                "action": normalized_action.value,
                "status": run.status,
                "revision": run.revision,
            },
        )
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


def _reopen_unstarted_downstream(match: Match) -> None:
    """Remove this match's stale winner from an unstarted downstream run."""
    if match.next_match_id is None or match.next_slot is None:
        return
    cleared = MatchSlot.objects.filter(
        match_id=match.next_match_id,
        slot_index=match.next_slot,
        upstream_match=match,
        resolution=MatchSlot.Resolution.PLAYER,
    ).update(
        participant=None,
        resolution=MatchSlot.Resolution.WAITING,
    )
    if not cleared:
        return

    downstream = Match.objects.get(pk=match.next_match_id)
    current = downstream.current_run
    if current is not None:
        if current.started_at is not None or current.status not in (
            MatchRun.Status.WAITING,
            MatchRun.Status.READY,
        ):
            raise AdminCommandPersistenceError(
                "a downstream run that has started cannot be reopened"
            )
        current.status = MatchRun.Status.SUPERSEDED
        current.revision += 1
        current.save(update_fields=("status", "revision"))
        MatchRunReady.objects.filter(run=current).delete()
    downstream.current_run = None
    downstream.status = Match.Status.WAITING
    downstream.winner = None
    downstream.save(update_fields=("current_run", "status", "winner", "updated_at"))


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

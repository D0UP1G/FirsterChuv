"""Pure guards and transition permits for administrator match actions.

The caller supplies trusted snapshots from the access and competition layers.
This module does not persist state, deduplicate command keys, or append events.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AdminActionError(ValueError):
    """Raised when an admin command is invalid for its trusted match snapshot."""


class RunStatus(StrEnum):
    WAITING = "WAITING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINALIZING = "FINALIZING"
    TIED = "TIED"
    FINISHED = "FINISHED"
    SUPERSEDED = "SUPERSEDED"


class AdminAction(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    EXTEND = "extend"
    TECHNICAL_RESULT = "technical_result"
    REMATCH = "rematch"
    REPLACE_PARTICIPANT = "replace_participant"


def _uuid(value: object, *, field: str) -> UUID:
    if not isinstance(value, (str, UUID)):
        raise AdminActionError(f"{field} must be a UUID")
    try:
        return UUID(str(value))
    except (ValueError, AttributeError) as error:
        raise AdminActionError(f"{field} must be a UUID") from error


def _required_text(value: object, *, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise AdminActionError(f"{field} must be non-empty and at most {max_length} characters")
    return value


@dataclass(frozen=True, slots=True)
class AdminActor:
    """Trusted server-side actor snapshot, never built from client role fields."""

    user_id: UUID | str
    role: str
    is_active: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _uuid(self.user_id, field="actor user ID"))
        if self.role != "admin":
            raise AdminActionError("match actions require the admin role")
        if type(self.is_active) is not bool or not self.is_active:
            raise AdminActionError("match actions require an active admin")


@dataclass(frozen=True, slots=True)
class AdminCommand:
    actor: AdminActor
    command_id: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actor, AdminActor):
            raise AdminActionError("actor must be a trusted AdminActor snapshot")
        object.__setattr__(
            self,
            "command_id",
            _required_text(self.command_id, field="command_id", max_length=128),
        )
        if self.reason is not None:
            object.__setattr__(
                self,
                "reason",
                _required_text(self.reason, field="reason", max_length=500),
            )


@dataclass(frozen=True, slots=True)
class MatchAdminSnapshot:
    """Trusted state needed for a pure administrative action decision."""

    match_id: UUID | str
    run_id: UUID | str | None
    run_status: RunStatus | str
    participant_user_ids: tuple[UUID | str | None, UUID | str | None]
    downstream_started: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "match_id", _uuid(self.match_id, field="match ID"))
        if self.run_id is not None:
            object.__setattr__(self, "run_id", _uuid(self.run_id, field="run ID"))
        try:
            object.__setattr__(self, "run_status", RunStatus(self.run_status))
        except (TypeError, ValueError) as error:
            raise AdminActionError("unknown run status") from error

        if not isinstance(self.participant_user_ids, (tuple, list)):
            raise AdminActionError("participant user IDs must contain two slots")
        if len(self.participant_user_ids) != 2:
            raise AdminActionError("participant user IDs must contain two slots")
        slots = tuple(
            None if user_id is None else _uuid(user_id, field="participant user ID")
            for user_id in self.participant_user_ids
        )
        occupied = [user_id for user_id in slots if user_id is not None]
        if len(set(occupied)) != len(occupied):
            raise AdminActionError("a participant cannot occupy both match slots")
        object.__setattr__(self, "participant_user_ids", slots)
        if type(self.downstream_started) is not bool:
            raise AdminActionError("downstream_started must be a boolean snapshot")


@dataclass(frozen=True, slots=True)
class ReplacementParticipant:
    """Trusted user snapshot for a participant joining a replacement slot."""

    user_id: UUID | str
    role: str
    is_active: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _uuid(self.user_id, field="replacement user ID"))
        if self.role != "participant":
            raise AdminActionError("replacement user must have participant role")
        if type(self.is_active) is not bool or not self.is_active:
            raise AdminActionError("replacement user must be active")


@dataclass(frozen=True, slots=True)
class AdminActionPlan:
    """Pure transition intent for a caller to persist atomically."""

    action: AdminAction
    match_id: UUID
    run_id: UUID | None
    expected_run_status: RunStatus
    run_status_after: RunStatus
    actor_user_id: UUID
    command_id: str
    reason: str | None
    winner_user_id: UUID | None = None
    extension_seconds: int | None = None
    slot_index: int | None = None
    replaced_user_id: UUID | None = None
    replacement_user_id: UUID | None = None
    supersede_current_run: bool = False
    new_run_required: bool = False
    carry_score_to_new_run: bool = False


def _require_reason(command: AdminCommand) -> str:
    if command.reason is None:
        raise AdminActionError("reason is required for this action")
    return command.reason


def _require_status(snapshot: MatchAdminSnapshot, allowed: frozenset[RunStatus]) -> None:
    if snapshot.run_status not in allowed:
        allowed_values = ", ".join(sorted(status.value for status in allowed))
        raise AdminActionError(
            "action is not allowed while run is "
            f"{snapshot.run_status.value}; expected {allowed_values}"
        )


def _require_run(snapshot: MatchAdminSnapshot) -> UUID:
    if snapshot.run_id is None:
        raise AdminActionError("action requires an existing match run")
    return snapshot.run_id


def _require_two_players(snapshot: MatchAdminSnapshot) -> tuple[UUID, UUID]:
    players = snapshot.participant_user_ids
    if any(user_id is None for user_id in players):
        raise AdminActionError("action requires both match slots to have participants")
    return players[0], players[1]  # type: ignore[return-value]


def _require_reviewable_downstream(snapshot: MatchAdminSnapshot) -> None:
    if snapshot.downstream_started:
        raise AdminActionError("result or participant cannot change after downstream match started")


def _plan(
    snapshot: MatchAdminSnapshot,
    command: AdminCommand,
    action: AdminAction,
    target_status: RunStatus,
    **changes: object,
) -> AdminActionPlan:
    plan_values: dict[str, object] = {
        "action": action,
        "match_id": snapshot.match_id,
        "run_id": snapshot.run_id,
        "expected_run_status": snapshot.run_status,
        "run_status_after": target_status,
        "actor_user_id": command.actor.user_id,
        "command_id": command.command_id,
        "reason": command.reason,
    }
    plan_values.update(changes)
    return AdminActionPlan(**plan_values)


def plan_pause(snapshot: MatchAdminSnapshot, command: AdminCommand) -> AdminActionPlan:
    _require_status(snapshot, frozenset((RunStatus.RUNNING,)))
    run_id = _require_run(snapshot)
    reason = _require_reason(command)
    return _plan(
        snapshot,
        command,
        AdminAction.PAUSE,
        RunStatus.PAUSED,
        run_id=run_id,
        reason=reason,
    )


def plan_resume(snapshot: MatchAdminSnapshot, command: AdminCommand) -> AdminActionPlan:
    _require_status(snapshot, frozenset((RunStatus.PAUSED,)))
    run_id = _require_run(snapshot)
    return _plan(
        snapshot,
        command,
        AdminAction.RESUME,
        RunStatus.RUNNING,
        run_id=run_id,
    )


def plan_extension(
    snapshot: MatchAdminSnapshot,
    command: AdminCommand,
    *,
    seconds: int,
    max_extension_seconds: int,
) -> AdminActionPlan:
    _require_status(snapshot, frozenset((RunStatus.RUNNING, RunStatus.PAUSED)))
    run_id = _require_run(snapshot)
    reason = _require_reason(command)
    if type(max_extension_seconds) is not int or max_extension_seconds <= 0:
        raise AdminActionError("max_extension_seconds must be a positive policy bound")
    if type(seconds) is not int or seconds <= 0 or seconds > max_extension_seconds:
        raise AdminActionError("extension seconds must be positive and within the policy bound")
    return _plan(
        snapshot,
        command,
        AdminAction.EXTEND,
        snapshot.run_status,
        run_id=run_id,
        reason=reason,
        extension_seconds=seconds,
    )


def plan_technical_result(
    snapshot: MatchAdminSnapshot,
    command: AdminCommand,
    *,
    winner_user_id: UUID | str,
) -> AdminActionPlan:
    _require_status(
        snapshot,
        frozenset(
            (
                RunStatus.READY,
                RunStatus.RUNNING,
                RunStatus.PAUSED,
                RunStatus.FINALIZING,
                RunStatus.TIED,
            )
        ),
    )
    run_id = _require_run(snapshot)
    players = _require_two_players(snapshot)
    reason = _require_reason(command)
    _require_reviewable_downstream(snapshot)
    winner = _uuid(winner_user_id, field="winner user ID")
    if winner not in players:
        raise AdminActionError("technical winner must be an active match participant")
    return _plan(
        snapshot,
        command,
        AdminAction.TECHNICAL_RESULT,
        RunStatus.FINISHED,
        run_id=run_id,
        reason=reason,
        winner_user_id=winner,
    )


def plan_rematch(
    snapshot: MatchAdminSnapshot,
    command: AdminCommand,
) -> AdminActionPlan:
    _require_status(
        snapshot,
        frozenset(
            (
                RunStatus.RUNNING,
                RunStatus.PAUSED,
                RunStatus.TIED,
                RunStatus.FINISHED,
            )
        ),
    )
    run_id = _require_run(snapshot)
    _require_two_players(snapshot)
    reason = _require_reason(command)
    _require_reviewable_downstream(snapshot)
    return _plan(
        snapshot,
        command,
        AdminAction.REMATCH,
        RunStatus.SUPERSEDED,
        run_id=run_id,
        reason=reason,
        supersede_current_run=True,
        new_run_required=True,
        carry_score_to_new_run=False,
    )


def plan_replacement(
    snapshot: MatchAdminSnapshot,
    command: AdminCommand,
    *,
    old_user_id: UUID | str,
    replacement: ReplacementParticipant,
) -> AdminActionPlan:
    old_user = _uuid(old_user_id, field="old user ID")
    if not isinstance(replacement, ReplacementParticipant):
        raise AdminActionError("replacement must be a trusted participant snapshot")
    if replacement.user_id in snapshot.participant_user_ids:
        raise AdminActionError("replacement user already occupies a match slot")
    try:
        slot_index = snapshot.participant_user_ids.index(old_user)
    except ValueError as error:
        raise AdminActionError("old user must occupy a match slot") from error
    reason = _require_reason(command)
    _require_reviewable_downstream(snapshot)

    if snapshot.run_status in (RunStatus.WAITING, RunStatus.READY):
        return _plan(
            snapshot,
            command,
            AdminAction.REPLACE_PARTICIPANT,
            snapshot.run_status,
            reason=reason,
            slot_index=slot_index,
            replaced_user_id=old_user,
            replacement_user_id=replacement.user_id,
        )

    _require_status(snapshot, frozenset((RunStatus.RUNNING, RunStatus.PAUSED)))
    run_id = _require_run(snapshot)
    _require_two_players(snapshot)
    _require_reviewable_downstream(snapshot)
    return _plan(
        snapshot,
        command,
        AdminAction.REPLACE_PARTICIPANT,
        RunStatus.SUPERSEDED,
        run_id=run_id,
        reason=reason,
        slot_index=slot_index,
        replaced_user_id=old_user,
        replacement_user_id=replacement.user_id,
        supersede_current_run=True,
        new_run_required=True,
        carry_score_to_new_run=False,
    )

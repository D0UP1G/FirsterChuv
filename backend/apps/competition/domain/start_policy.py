"""Pure readiness and auto-start policy for one two-player match run."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from backend.apps.competition.domain.clock import (
    ClockRunStatus,
    ClockSnapshot,
    start_clock,
)


class StartPolicyError(ValueError):
    """Raised when a readiness signal is invalid for this match run."""


class StartMode(StrEnum):
    MANUAL = "manual"
    BOTH_READY = "both_ready"


@dataclass(frozen=True, slots=True)
class MatchStartState:
    """Immutable inputs and current clock state for the match start gate."""

    start_mode: StartMode
    participant_user_ids: tuple[str, str]
    ready_user_ids: frozenset[str]
    clock: ClockSnapshot

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "start_mode", StartMode(self.start_mode))
        except ValueError as error:
            raise StartPolicyError("unknown match start mode") from error

        participants = self.participant_user_ids
        if (
            not isinstance(participants, tuple)
            or len(participants) != 2
            or any(not isinstance(user_id, str) or not user_id.strip() for user_id in participants)
            or len(set(participants)) != 2
        ):
            raise StartPolicyError("exactly two unique participant IDs are required")

        if not isinstance(self.clock, ClockSnapshot):
            raise StartPolicyError("clock must be a ClockSnapshot")

        try:
            ready_user_ids = frozenset(self.ready_user_ids)
        except TypeError as error:
            raise StartPolicyError("ready user IDs must be a collection") from error
        if any(
            not isinstance(user_id, str) or not user_id.strip()
            for user_id in ready_user_ids
        ):
            raise StartPolicyError("ready user IDs must be non-empty strings")
        if not ready_user_ids <= set(participants):
            raise StartPolicyError("only match participants can be ready")
        if self.clock.status is ClockRunStatus.WAITING and ready_user_ids:
            raise StartPolicyError("a WAITING run cannot have ready participants")
        object.__setattr__(self, "ready_user_ids", ready_user_ids)


def mark_player_ready(
    state: MatchStartState,
    participant_user_id: str,
    now: datetime,
) -> MatchStartState:
    """Record readiness and auto-start exactly when both players are ready.

    A repeated readiness command is idempotent, including after the run starts.
    The persistence service should call this function inside the transaction
    that saves the ready set and clock transition.
    """
    if not isinstance(state, MatchStartState):
        raise StartPolicyError("state must be a MatchStartState")
    if (
        not isinstance(participant_user_id, str)
        or not participant_user_id.strip()
    ):
        raise StartPolicyError("participant user ID must be a non-empty string")
    if participant_user_id not in state.participant_user_ids:
        raise StartPolicyError("only match participants can become ready")
    if participant_user_id in state.ready_user_ids:
        return state
    if state.clock.status is not ClockRunStatus.READY:
        raise StartPolicyError("participants can become ready only for a READY run")
    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise StartPolicyError("start time must be timezone-aware")

    ready_user_ids = state.ready_user_ids | {participant_user_id}
    updated = replace(state, ready_user_ids=ready_user_ids)
    if (
        updated.start_mode is StartMode.BOTH_READY
        and set(updated.participant_user_ids) <= ready_user_ids
    ):
        updated = replace(updated, clock=start_clock(updated.clock, now))
    return updated

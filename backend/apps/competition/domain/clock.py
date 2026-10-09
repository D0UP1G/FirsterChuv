"""Authoritative match-clock arithmetic and state transitions.

This module has no Django dependency so clock rules can be exercised and
reviewed independently of task-package and HTTP integration.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum


class ClockError(ValueError):
    """Raised when a clock snapshot or transition violates the clock rules."""


class ClockRunStatus(StrEnum):
    WAITING = "WAITING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINALIZING = "FINALIZING"
    FINISHED = "FINISHED"
    TIED = "TIED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class ClockSnapshot:
    """Clock fields needed to evaluate or transition one persisted match run."""

    status: ClockRunStatus
    allowed_duration_ms: int
    started_at: datetime | None = None
    paused_at: datetime | None = None
    accumulated_pause_ms: int = 0

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "status", ClockRunStatus(self.status))
        except ValueError as error:
            raise ClockError("unknown match-run status") from error

        if type(self.allowed_duration_ms) is not int or self.allowed_duration_ms < 1:
            raise ClockError("allowed duration must be a positive integer")
        if type(self.accumulated_pause_ms) is not int or self.accumulated_pause_ms < 0:
            raise ClockError("accumulated pause must be a non-negative integer")
        for value in (self.started_at, self.paused_at):
            if value is not None:
                _require_aware(value)
        if self.paused_at is not None and self.status is not ClockRunStatus.PAUSED:
            raise ClockError("paused_at is only valid while the run is paused")
        if self.status is ClockRunStatus.PAUSED and self.paused_at is None:
            raise ClockError("a paused run must have paused_at")
        if self.paused_at is not None and self.started_at is None:
            raise ClockError("a paused run must have started_at")
        if self.paused_at is not None and self.started_at is not None:
            elapsed_before_pause_ms = _duration_ms(self.started_at, self.paused_at)
            if self.accumulated_pause_ms > elapsed_before_pause_ms:
                raise ClockError("accumulated pause exceeds elapsed wall time")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ClockError("clock timestamps must be timezone-aware")


def _duration_ms(start: datetime, end: datetime) -> int:
    _require_aware(start)
    _require_aware(end)
    try:
        delta: timedelta = end - start
    except TypeError as error:
        raise ClockError("clock timestamps must use compatible timezones") from error
    if delta < timedelta(0):
        raise ClockError("clock time cannot move backwards")
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


def active_elapsed_ms(snapshot: ClockSnapshot, now: datetime) -> int:
    """Return whole active milliseconds, excluding completed and current pauses."""
    if snapshot.status in (ClockRunStatus.WAITING, ClockRunStatus.READY):
        if snapshot.started_at is not None:
            raise ClockError("an unstarted run cannot have started_at")
        return 0
    if snapshot.status not in (ClockRunStatus.RUNNING, ClockRunStatus.PAUSED):
        raise ClockError("active elapsed time is unavailable for this run status")
    if snapshot.started_at is None:
        raise ClockError("a started run must have started_at")

    endpoint = snapshot.paused_at if snapshot.status is ClockRunStatus.PAUSED else now
    assert endpoint is not None
    wall_elapsed_ms = _duration_ms(snapshot.started_at, endpoint)
    elapsed_ms = wall_elapsed_ms - snapshot.accumulated_pause_ms
    if elapsed_ms < 0:
        raise ClockError("accumulated pause exceeds elapsed wall time")
    return elapsed_ms


def start_clock(snapshot: ClockSnapshot, now: datetime) -> ClockSnapshot:
    """Start a READY run once; retries after start are rejected by state."""
    _require_aware(now)
    if snapshot.status is not ClockRunStatus.READY or snapshot.started_at is not None:
        raise ClockError("only an unstarted READY run can start")
    return replace(snapshot, status=ClockRunStatus.RUNNING, started_at=now)


def pause_clock(snapshot: ClockSnapshot, now: datetime) -> ClockSnapshot:
    """Pause a running clock without changing its accumulated pause total."""
    _require_aware(now)
    if snapshot.status is not ClockRunStatus.RUNNING or snapshot.started_at is None:
        raise ClockError("only a RUNNING run can be paused")
    if active_elapsed_ms(snapshot, now) >= snapshot.allowed_duration_ms:
        raise ClockError("deadline has passed")
    return replace(snapshot, status=ClockRunStatus.PAUSED, paused_at=now)


def resume_clock(snapshot: ClockSnapshot, now: datetime) -> ClockSnapshot:
    """Resume a paused run and add its completed pause interval exactly once."""
    _require_aware(now)
    if snapshot.status is not ClockRunStatus.PAUSED or snapshot.paused_at is None:
        raise ClockError("only a PAUSED run can be resumed")
    pause_ms = _duration_ms(snapshot.paused_at, now)
    return replace(
        snapshot,
        status=ClockRunStatus.RUNNING,
        paused_at=None,
        accumulated_pause_ms=snapshot.accumulated_pause_ms + pause_ms,
    )


def submission_elapsed_ms(snapshot: ClockSnapshot, now: datetime) -> int:
    """Return accepted server elapsed time or reject closed/late submissions."""
    if snapshot.status is not ClockRunStatus.RUNNING:
        raise ClockError("submissions are accepted only while the run is RUNNING")
    elapsed_ms = active_elapsed_ms(snapshot, now)
    if elapsed_ms >= snapshot.allowed_duration_ms:
        raise ClockError("submission deadline has passed")
    return elapsed_ms


def reconcile_deadline(snapshot: ClockSnapshot, now: datetime) -> ClockSnapshot:
    """Move an expired RUNNING run to FINALIZING; repeated ticks are harmless."""
    if snapshot.status is not ClockRunStatus.RUNNING:
        return snapshot
    elapsed_ms = active_elapsed_ms(snapshot, now)
    if elapsed_ms < snapshot.allowed_duration_ms:
        return snapshot
    return replace(snapshot, status=ClockRunStatus.FINALIZING)

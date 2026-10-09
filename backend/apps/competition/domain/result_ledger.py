"""Pure accepted-attempt and idempotent result ledger for one match run."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from backend.apps.common.contracts import (
    AttemptReceipt,
    ResultApplication,
    ResultReceipt,
)
from backend.apps.competition.domain.scoring import (
    MatchScore,
    ScoreRules,
    ScoredAttempt,
    calculate_match_score,
)


class ResultLedgerError(ValueError):
    """Raised when an accepted receipt or result violates ledger invariants."""


@dataclass(frozen=True, slots=True)
class LedgerAttempt:
    """Immutable accepted identity plus its optional final result receipt."""

    accepted: AttemptReceipt
    result: ResultReceipt | None = None


@dataclass(frozen=True, slots=True)
class ResultLedger:
    """Accepted attempts and scoring inputs frozen for one immutable run."""

    run_id: UUID
    participant_user_ids: tuple[UUID, UUID]
    problem_ids: tuple[UUID, ...]
    scoring_version: str
    rules: ScoreRules
    attempts: tuple[LedgerAttempt, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, UUID):
            raise ResultLedgerError("run_id must be a UUID")
        if (
            not isinstance(self.participant_user_ids, tuple)
            or len(self.participant_user_ids) != 2
            or any(not isinstance(user_id, UUID) for user_id in self.participant_user_ids)
            or len(set(self.participant_user_ids)) != 2
        ):
            raise ResultLedgerError("exactly two unique participant UUIDs are required")
        if (
            not isinstance(self.problem_ids, tuple)
            or not self.problem_ids
            or any(not isinstance(problem_id, UUID) for problem_id in self.problem_ids)
            or len(set(self.problem_ids)) != len(self.problem_ids)
        ):
            raise ResultLedgerError("problem IDs must be a non-empty unique UUID tuple")
        if not isinstance(self.scoring_version, str) or not self.scoring_version.strip():
            raise ResultLedgerError("scoring_version must be non-empty")
        if not isinstance(self.rules, ScoreRules):
            raise ResultLedgerError("rules must be an immutable ScoreRules snapshot")
        if not isinstance(self.attempts, tuple):
            raise ResultLedgerError("attempts must be an immutable tuple")

        seen_submission_ids: set[UUID] = set()
        for attempt in self.attempts:
            if not isinstance(attempt, LedgerAttempt):
                raise ResultLedgerError("attempts must contain LedgerAttempt values")
            receipt = attempt.accepted
            _validate_attempt_receipt(self, receipt)
            if receipt.submission_id in seen_submission_ids:
                raise ResultLedgerError("submission IDs must be unique in a run ledger")
            seen_submission_ids.add(receipt.submission_id)
            if attempt.result is not None:
                _validate_result_matches_acceptance(receipt, attempt.result)

    @property
    def pending_submission_ids(self) -> tuple[UUID, ...]:
        """Accepted work without a final result; FINALIZING must wait for it."""
        return tuple(
            attempt.accepted.submission_id
            for attempt in self.attempts
            if attempt.result is None
        )


@dataclass(frozen=True, slots=True)
class ResultTransition:
    """One idempotent result delivery and its recomputed run score."""

    ledger: ResultLedger
    application: ResultApplication
    score: MatchScore | None
    can_finalize: bool


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ResultLedgerError(f"{field_name} must be timezone-aware")


def _validate_attempt_receipt(
    ledger: ResultLedger,
    receipt: AttemptReceipt,
) -> None:
    if not isinstance(receipt, AttemptReceipt):
        raise ResultLedgerError("accepted value must be an AttemptReceipt")
    for field_name in ("submission_id", "run_id", "user_id", "problem_id"):
        if not isinstance(getattr(receipt, field_name), UUID):
            raise ResultLedgerError(f"{field_name} must be a UUID")
    if not isinstance(receipt.received_at, datetime):
        raise ResultLedgerError("received_at must be a datetime")
    _require_aware(receipt.received_at, "received_at")
    if type(receipt.elapsed_ms) is not int or receipt.elapsed_ms < 0:
        raise ResultLedgerError("elapsed_ms must be a non-negative integer")
    if not isinstance(receipt.scoring_version, str) or not receipt.scoring_version.strip():
        raise ResultLedgerError("receipt scoring_version must be non-empty")
    if receipt.run_id != ledger.run_id:
        raise ResultLedgerError("accepted receipt belongs to another run")
    if receipt.user_id not in ledger.participant_user_ids:
        raise ResultLedgerError("accepted receipt belongs to a non-participant")
    if receipt.problem_id not in ledger.problem_ids:
        raise ResultLedgerError("accepted receipt references a problem outside this run")
    if receipt.scoring_version != ledger.scoring_version:
        raise ResultLedgerError("accepted receipt scoring_version differs from run snapshot")


def _validate_result_matches_acceptance(
    accepted: AttemptReceipt,
    result: ResultReceipt,
) -> None:
    if not isinstance(result, ResultReceipt):
        raise ResultLedgerError("result value must be a ResultReceipt")
    for field_name in ("submission_id", "run_id", "user_id", "problem_id"):
        if not isinstance(getattr(result, field_name), UUID):
            raise ResultLedgerError(f"result {field_name} must be a UUID")
    if not isinstance(result.received_at, datetime):
        raise ResultLedgerError("result received_at must be a datetime")
    _require_aware(result.received_at, "result received_at")
    if type(result.elapsed_ms) is not int or result.elapsed_ms < 0:
        raise ResultLedgerError("result elapsed_ms must be a non-negative integer")
    receipt_identity = (
        result.submission_id,
        result.run_id,
        result.user_id,
        result.problem_id,
        result.received_at,
        result.elapsed_ms,
        result.scoring_version,
    )
    accepted_identity = (
        accepted.submission_id,
        accepted.run_id,
        accepted.user_id,
        accepted.problem_id,
        accepted.received_at,
        accepted.elapsed_ms,
        accepted.scoring_version,
    )
    if receipt_identity != accepted_identity:
        raise ResultLedgerError("result identity or timing differs from accepted receipt")

    # Reuse the score-domain validator so malformed verdicts never enter the ledger.
    try:
        _scored_attempt(result)
    except (TypeError, ValueError) as error:
        raise ResultLedgerError("result verdict is invalid") from error


def _scored_attempt(receipt: ResultReceipt) -> ScoredAttempt:
    return ScoredAttempt(
        submission_id=str(receipt.submission_id),
        run_id=str(receipt.run_id),
        user_id=str(receipt.user_id),
        problem_id=str(receipt.problem_id),
        received_at=receipt.received_at,
        elapsed_ms=receipt.elapsed_ms,
        verdict=receipt.verdict,
    )


def _current_score(ledger: ResultLedger) -> MatchScore:
    return calculate_match_score(
        run_id=str(ledger.run_id),
        participant_user_ids=tuple(map(str, ledger.participant_user_ids)),
        problem_ids=tuple(map(str, ledger.problem_ids)),
        results=(
            _scored_attempt(attempt.result)
            for attempt in ledger.attempts
            if attempt.result is not None
        ),
        rules=ledger.rules,
    )


def register_accepted(
    ledger: ResultLedger,
    receipt: AttemptReceipt,
) -> ResultLedger:
    """Record an immutable accepted receipt; an identical retry is a no-op."""
    if not isinstance(ledger, ResultLedger):
        raise ResultLedgerError("ledger must be a ResultLedger")
    _validate_attempt_receipt(ledger, receipt)
    previous = next(
        (
            attempt
            for attempt in ledger.attempts
            if attempt.accepted.submission_id == receipt.submission_id
        ),
        None,
    )
    if previous is not None:
        if previous.accepted == receipt:
            return ledger
        raise ResultLedgerError("submission_id already has a different accepted receipt")
    return replace(ledger, attempts=(*ledger.attempts, LedgerAttempt(accepted=receipt)))


def apply_result(
    ledger: ResultLedger,
    receipt: ResultReceipt,
    *,
    current_run_id: UUID,
) -> ResultTransition:
    """Store one final result and recalculate only if its run remains current.

    The caller loads this run's ledger under the match transaction and supplies
    the persisted current run ID. A stale result is stored idempotently but is
    never applied to the replacement run's score.
    """
    if not isinstance(ledger, ResultLedger):
        raise ResultLedgerError("ledger must be a ResultLedger")
    if not isinstance(current_run_id, UUID):
        raise ResultLedgerError("current_run_id must be a UUID")
    if not isinstance(receipt, ResultReceipt):
        raise ResultLedgerError("result value must be a ResultReceipt")
    attempt_index = next(
        (
            index
            for index, attempt in enumerate(ledger.attempts)
            if attempt.accepted.submission_id == receipt.submission_id
        ),
        None,
    )
    if attempt_index is None:
        raise ResultLedgerError("result has no accepted ledger receipt")

    attempt = ledger.attempts[attempt_index]
    _validate_result_matches_acceptance(attempt.accepted, receipt)
    if attempt.result is not None:
        if attempt.result != receipt:
            raise ResultLedgerError("submission_id already has a conflicting result")
        current = current_run_id == ledger.run_id
        return ResultTransition(
            ledger=ledger,
            application=ResultApplication(applied=False),
            score=_current_score(ledger) if current else None,
            can_finalize=current and not ledger.pending_submission_ids,
        )

    attempts = list(ledger.attempts)
    attempts[attempt_index] = replace(attempt, result=receipt)
    updated = replace(ledger, attempts=tuple(attempts))
    current = current_run_id == ledger.run_id
    return ResultTransition(
        ledger=updated,
        application=ResultApplication(applied=current),
        score=_current_score(updated) if current else None,
        can_finalize=current and not updated.pending_submission_ids,
    )

"""Pure deterministic scoring for one completed match run.

The caller supplies persisted, final verdict receipts for the exact run. This
module does not decide admission, worker lease ownership, or when a run may be
finalized; those checks belong to the ledger/ResultSink transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Iterable


class ScoreInputError(ValueError):
    """Raised when receipts do not describe one valid match-run score input."""


class Verdict(StrEnum):
    OK = "OK"
    WA = "WA"
    TL = "TL"
    ML = "ML"
    RE = "RE"
    CE = "CE"


class ProblemOutcome(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ATTEMPTED = "ATTEMPTED"
    SOLVED = "SOLVED"


class FinalTiePolicy(StrEnum):
    REMATCH = "rematch"


PENALTY_ELIGIBLE_VERDICTS = frozenset(
    (Verdict.WA, Verdict.TL, Verdict.ML, Verdict.RE)
)


@dataclass(frozen=True, slots=True)
class ScoreRules:
    """Immutable scoring snapshot for a run; the criterion order is fixed."""

    wrong_attempt_penalty_ms: int = 60_000
    penalized_verdicts: tuple[Verdict, ...] = (
        Verdict.WA,
        Verdict.TL,
        Verdict.ML,
        Verdict.RE,
    )
    final_tie_policy: FinalTiePolicy = FinalTiePolicy.REMATCH

    def __post_init__(self) -> None:
        if (
            type(self.wrong_attempt_penalty_ms) is not int
            or self.wrong_attempt_penalty_ms < 0
        ):
            raise ScoreInputError("wrong-attempt penalty must be a non-negative integer")

        try:
            verdicts = tuple(Verdict(verdict) for verdict in self.penalized_verdicts)
            tie_policy = FinalTiePolicy(self.final_tie_policy)
        except ValueError as error:
            raise ScoreInputError("unknown verdict or final tie policy") from error
        if len(set(verdicts)) != len(verdicts):
            raise ScoreInputError("penalized verdicts must be unique")
        if not set(verdicts) <= PENALTY_ELIGIBLE_VERDICTS:
            raise ScoreInputError("only WA, TL, ML, and RE can be penalized")
        object.__setattr__(self, "penalized_verdicts", verdicts)
        object.__setattr__(self, "final_tie_policy", tie_policy)


@dataclass(frozen=True, slots=True)
class ScoredAttempt:
    """One accepted submission's final judge result, with server timestamps."""

    submission_id: str
    run_id: str
    user_id: str
    problem_id: str
    received_at: datetime
    elapsed_ms: int
    verdict: Verdict

    def __post_init__(self) -> None:
        for field_name in ("submission_id", "run_id", "user_id", "problem_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ScoreInputError(f"{field_name} must be a non-empty string")
        if type(self.elapsed_ms) is not int or self.elapsed_ms < 0:
            raise ScoreInputError("elapsed_ms must be a non-negative integer")
        if (
            not isinstance(self.received_at, datetime)
            or self.received_at.tzinfo is None
            or self.received_at.utcoffset() is None
        ):
            raise ScoreInputError("received_at must be timezone-aware")
        try:
            object.__setattr__(self, "verdict", Verdict(self.verdict))
        except ValueError as error:
            raise ScoreInputError("unknown final verdict") from error


@dataclass(frozen=True, slots=True)
class ProblemScore:
    problem_id: str
    outcome: ProblemOutcome
    attempts: int
    last_verdict: Verdict | None
    first_ok_elapsed_ms: int | None
    penalized_attempts_before_first_ok: int


@dataclass(frozen=True, slots=True)
class ParticipantScore:
    user_id: str
    solved_count: int
    penalty_ms: int
    last_accepted_elapsed_ms: int | None
    problems: tuple[ProblemScore, ...]


@dataclass(frozen=True, slots=True)
class MatchScore:
    run_id: str
    winner_user_id: str | None
    tied: bool
    rematch_required: bool
    participants: tuple[ParticipantScore, ParticipantScore]


def _validate_ids(ids: tuple[str, ...], name: str, expected_count: int | None) -> None:
    if expected_count is not None and len(ids) != expected_count:
        raise ScoreInputError(f"exactly {expected_count} {name} are required")
    if any(not isinstance(value, str) or not value.strip() for value in ids):
        raise ScoreInputError(f"{name} must be non-empty strings")
    if len(set(ids)) != len(ids):
        raise ScoreInputError(f"{name} must be unique")


def _timeline_key(attempt: ScoredAttempt) -> tuple[int, datetime, str]:
    # elapsed_ms is authoritative; received_at orders submissions quantized to
    # the same millisecond. submission_id makes the order deterministic on ties.
    return (attempt.elapsed_ms, attempt.received_at, attempt.submission_id)


def _unique_receipts(receipts: Iterable[ScoredAttempt]) -> tuple[ScoredAttempt, ...]:
    by_submission_id: dict[str, ScoredAttempt] = {}
    for receipt in receipts:
        if not isinstance(receipt, ScoredAttempt):
            raise ScoreInputError("all result receipts must be ScoredAttempt values")
        previous = by_submission_id.get(receipt.submission_id)
        if previous is not None and previous != receipt:
            raise ScoreInputError("one submission_id cannot describe conflicting results")
        by_submission_id[receipt.submission_id] = receipt
    return tuple(by_submission_id.values())


def _score_participant(
    user_id: str,
    problem_ids: tuple[str, ...],
    attempts_by_problem: dict[str, list[ScoredAttempt]],
    rules: ScoreRules,
) -> ParticipantScore:
    problems: list[ProblemScore] = []
    solved_elapsed: list[int] = []
    penalty_ms = 0
    penalized_verdicts = set(rules.penalized_verdicts)

    for problem_id in problem_ids:
        attempts = sorted(attempts_by_problem.get(problem_id, ()), key=_timeline_key)
        if not attempts:
            problems.append(
                ProblemScore(
                    problem_id=problem_id,
                    outcome=ProblemOutcome.NOT_STARTED,
                    attempts=0,
                    last_verdict=None,
                    first_ok_elapsed_ms=None,
                    penalized_attempts_before_first_ok=0,
                )
            )
            continue

        first_ok_index = next(
            (index for index, attempt in enumerate(attempts) if attempt.verdict is Verdict.OK),
            None,
        )
        penalized_before_first_ok = (
            sum(
                attempt.verdict in penalized_verdicts
                for attempt in attempts[:first_ok_index]
            )
            if first_ok_index is not None
            else 0
        )
        first_ok_elapsed = (
            attempts[first_ok_index].elapsed_ms if first_ok_index is not None else None
        )

        if first_ok_elapsed is not None:
            solved_elapsed.append(first_ok_elapsed)
            penalty_ms += (
                first_ok_elapsed
                + penalized_before_first_ok * rules.wrong_attempt_penalty_ms
            )
            outcome = ProblemOutcome.SOLVED
        else:
            outcome = ProblemOutcome.ATTEMPTED

        problems.append(
            ProblemScore(
                problem_id=problem_id,
                outcome=outcome,
                attempts=len(attempts),
                last_verdict=attempts[-1].verdict,
                first_ok_elapsed_ms=first_ok_elapsed,
                penalized_attempts_before_first_ok=penalized_before_first_ok,
            )
        )

    return ParticipantScore(
        user_id=user_id,
        solved_count=len(solved_elapsed),
        penalty_ms=penalty_ms,
        last_accepted_elapsed_ms=max(solved_elapsed) if solved_elapsed else None,
        problems=tuple(problems),
    )


def calculate_match_score(
    *,
    run_id: str,
    participant_user_ids: tuple[str, str],
    problem_ids: tuple[str, ...],
    results: Iterable[ScoredAttempt],
    rules: ScoreRules,
) -> MatchScore:
    """Compute winner using solved ↓, penalty ↑, and last accepted time ↑.

    Only first OK per problem scores. Wrong attempts count only when they occur
    before that first OK; unsolved-task attempts, later OKs, and CE do not add
    penalty. Repeated identical submission receipts are ignored.
    """
    _validate_ids(participant_user_ids, "participant user IDs", 2)
    _validate_ids(problem_ids, "problem IDs", None)
    if not problem_ids:
        raise ScoreInputError("at least one problem is required")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ScoreInputError("run_id must be a non-empty string")
    if not isinstance(rules, ScoreRules):
        raise ScoreInputError("rules must be a ScoreRules snapshot")

    allowed_users = set(participant_user_ids)
    allowed_problems = set(problem_ids)
    attempts_by_pair: dict[tuple[str, str], list[ScoredAttempt]] = {}
    for receipt in _unique_receipts(results):
        if receipt.run_id != run_id:
            raise ScoreInputError("result receipt belongs to another run")
        if receipt.user_id not in allowed_users:
            raise ScoreInputError("result receipt belongs to a non-participant")
        if receipt.problem_id not in allowed_problems:
            raise ScoreInputError("result receipt references a problem outside this run")
        attempts_by_pair.setdefault((receipt.user_id, receipt.problem_id), []).append(receipt)

    scores = tuple(
        _score_participant(
            user_id,
            problem_ids,
            {
                problem_id: attempts_by_pair.get((user_id, problem_id), [])
                for problem_id in problem_ids
            },
            rules,
        )
        for user_id in participant_user_ids
    )
    left, right = scores
    left_rank = (
        -left.solved_count,
        left.penalty_ms,
        left.last_accepted_elapsed_ms if left.last_accepted_elapsed_ms is not None else 0,
    )
    right_rank = (
        -right.solved_count,
        right.penalty_ms,
        right.last_accepted_elapsed_ms if right.last_accepted_elapsed_ms is not None else 0,
    )
    tied = left_rank == right_rank
    winner = None if tied else (left.user_id if left_rank < right_rank else right.user_id)
    return MatchScore(
        run_id=run_id,
        winner_user_id=winner,
        tied=tied,
        rematch_required=tied and rules.final_tie_policy is FinalTiePolicy.REMATCH,
        participants=(left, right),
    )

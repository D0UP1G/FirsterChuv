"""Durable adapter for the pure accepted/result ledger transitions."""

from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, models, transaction

from backend.apps.common.contracts import AttemptReceipt, ResultReceipt
from backend.apps.competition.domain.clock import ClockRunStatus, ClockSnapshot, submission_elapsed_ms
from backend.apps.competition.domain.result_ledger import (
    LedgerAttempt,
    ResultLedger,
    ResultLedgerError,
    apply_result as apply_result_transition,
    register_accepted as register_accepted_transition,
)
from backend.apps.competition.domain.scoring import FinalTiePolicy, ScoreRules, Verdict
from backend.apps.competition.models import AcceptedAttempt, AttemptResult, Match, MatchRun


class LedgerPersistenceError(RuntimeError):
    """The persisted receipt cannot be admitted or applied safely."""

    status_code = 409
    code = "ledger_conflict"


def _claim_run(run_id: UUID) -> MatchRun:
    changed = MatchRun.objects.filter(pk=run_id).update(revision=models.F("revision"))
    if not changed:
        raise LedgerPersistenceError("match run was not found")
    return MatchRun.objects.select_related("match").get(pk=run_id)


def _rules(run: MatchRun) -> ScoreRules:
    snapshot = run.score_rule
    try:
        return ScoreRules(
            wrong_attempt_penalty_ms=snapshot["wrongAttemptPenaltySec"] * 1000,
            penalized_verdicts=tuple(Verdict(value) for value in snapshot["penalizedVerdicts"]),
            final_tie_policy=FinalTiePolicy(snapshot["finalTiePolicy"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise LedgerPersistenceError("run scoring snapshot is invalid") from error


def _ledger(run: MatchRun) -> ResultLedger:
    participants = tuple(UUID(str(value)) for value in run.participant_user_ids)
    problems = tuple(UUID(item["problemId"]) for item in run.problem_versions)
    try:
        ledger = ResultLedger(
            run_id=run.pk,
            participant_user_ids=participants,
            problem_ids=problems,
            scoring_version=run.scoring_version,
            rules=_rules(run),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise LedgerPersistenceError("run snapshot cannot initialize its result ledger") from error

    rows = list(
        AcceptedAttempt.objects.filter(run=run)
        .select_related("result")
        .order_by("received_at", "submission_id")
    )
    for row in rows:
        accepted = AttemptReceipt(
            submission_id=row.submission_id,
            run_id=row.run_id,
            user_id=row.user_id,
            problem_id=row.problem_id,
            received_at=row.received_at,
            elapsed_ms=row.elapsed_ms,
            scoring_version=row.scoring_version,
        )
        result = None
        if hasattr(row, "result"):
            result = ResultReceipt(
                submission_id=accepted.submission_id,
                run_id=accepted.run_id,
                user_id=accepted.user_id,
                problem_id=accepted.problem_id,
                received_at=accepted.received_at,
                elapsed_ms=accepted.elapsed_ms,
                scoring_version=accepted.scoring_version,
                verdict=row.result.verdict,
            )
        try:
            ledger = register_accepted_transition(ledger, accepted)
            if result is not None:
                ledger = apply_result_transition(
                    ledger,
                    result,
                    current_run_id=run.match.current_run_id or run.pk,
                ).ledger
        except ResultLedgerError as error:
            raise LedgerPersistenceError("stored receipts violate run ledger invariants") from error
    return ledger


def _receipt_matches(existing: AcceptedAttempt, receipt: AttemptReceipt) -> bool:
    return (
        existing.run_id == receipt.run_id
        and existing.user_id == receipt.user_id
        and existing.problem_id == receipt.problem_id
        and existing.received_at == receipt.received_at
        and existing.elapsed_ms == receipt.elapsed_ms
        and existing.scoring_version == receipt.scoring_version
    )


@transaction.atomic
def register_accepted(receipt: AttemptReceipt) -> AcceptedAttempt:
    """Persist admission before returning success; exact retries are no-ops."""
    if not isinstance(receipt, AttemptReceipt):
        raise LedgerPersistenceError("accepted receipt has an invalid type")
    existing = AcceptedAttempt.objects.filter(pk=receipt.submission_id).first()
    if existing is not None:
        if _receipt_matches(existing, receipt):
            return existing
        raise LedgerPersistenceError("submission_id already has a conflicting accepted receipt")

    run = _claim_run(receipt.run_id)
    Match.objects.filter(pk=run.match_id).update(updated_at=models.F("updated_at"))
    run.match.refresh_from_db()
    if run.match.current_run_id != run.pk or run.status != MatchRun.Status.RUNNING:
        raise LedgerPersistenceError("only the current running match can accept a receipt")
    try:
        elapsed = submission_elapsed_ms(
            ClockSnapshot(
                status=run.status,
                allowed_duration_ms=run.allowed_duration_ms,
                started_at=run.started_at,
                paused_at=run.paused_at,
                accumulated_pause_ms=run.accumulated_pause_ms,
            ),
            receipt.received_at,
        )
    except ValueError as error:
        raise LedgerPersistenceError(str(error)) from error
    if elapsed != receipt.elapsed_ms:
        raise LedgerPersistenceError("receipt elapsed_ms differs from the server clock")
    try:
        ledger = register_accepted_transition(_ledger(run), receipt)
    except ResultLedgerError as error:
        raise LedgerPersistenceError(str(error)) from error
    try:
        with transaction.atomic():
            return AcceptedAttempt.objects.create(
                submission_id=receipt.submission_id,
                run=run,
                user_id=receipt.user_id,
                problem_id=receipt.problem_id,
                received_at=receipt.received_at,
                elapsed_ms=receipt.elapsed_ms,
                scoring_version=receipt.scoring_version,
            )
    except IntegrityError as error:
        # A concurrent same-ID admission is safe only when the durable identity matches.
        existing = AcceptedAttempt.objects.filter(pk=receipt.submission_id).first()
        if existing is not None and _receipt_matches(existing, receipt):
            return existing
        raise LedgerPersistenceError("submission_id was concurrently claimed") from error


def _score_payload(score) -> dict:
    return {
        "runId": score.run_id,
        "winnerUserId": score.winner_user_id,
        "tied": score.tied,
        "rematchRequired": score.rematch_required,
        "participants": [
            {
                "userId": participant.user_id,
                "solvedCount": participant.solved_count,
                "penaltyMs": participant.penalty_ms,
                "lastAcceptedElapsedMs": participant.last_accepted_elapsed_ms,
                "problems": [
                    {
                        "problemId": problem.problem_id,
                        "outcome": problem.outcome.value,
                        "attempts": problem.attempts,
                        "lastVerdict": problem.last_verdict.value if problem.last_verdict else None,
                        "firstOkElapsedMs": problem.first_ok_elapsed_ms,
                        "penalizedAttemptsBeforeFirstOk": problem.penalized_attempts_before_first_ok,
                    }
                    for problem in participant.problems
                ],
            }
            for participant in score.participants
        ],
    }


@transaction.atomic
def apply_result(receipt: ResultReceipt) -> bool:
    """Durably record one verdict and atomically refresh only the current run score."""
    if not isinstance(receipt, ResultReceipt):
        raise LedgerPersistenceError("result receipt has an invalid type")
    accepted = AcceptedAttempt.objects.filter(pk=receipt.submission_id).select_related("run__match").first()
    if accepted is None:
        raise LedgerPersistenceError("result has no accepted receipt")
    run = _claim_run(accepted.run_id)
    Match.objects.filter(pk=run.match_id).update(updated_at=models.F("updated_at"))
    run.match.refresh_from_db()
    ledger = _ledger(run)
    try:
        transition = apply_result_transition(
            ledger,
            receipt,
            current_run_id=run.match.current_run_id or UUID(int=0),
        )
    except ResultLedgerError as error:
        raise LedgerPersistenceError(str(error)) from error

    result, created = AttemptResult.objects.get_or_create(
        accepted=accepted,
        defaults={"verdict": receipt.verdict},
    )
    if not created and result.verdict != receipt.verdict:
        raise LedgerPersistenceError("submission_id already has a conflicting result")
    if transition.application.applied and transition.score is not None:
        run.score_snapshot = _score_payload(transition.score)
        run.revision += 1
        run.save(update_fields=("score_snapshot", "revision"))
    return transition.application.applied

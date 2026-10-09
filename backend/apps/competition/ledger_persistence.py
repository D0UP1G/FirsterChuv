"""Durable adapter for the pure accepted/result ledger transitions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.common.contracts import AttemptReceipt, ResultReceipt
from backend.apps.competition.domain.clock import (
    ClockRunStatus,
    ClockSnapshot,
    reconcile_deadline,
    submission_elapsed_ms,
)
from backend.apps.competition.domain.result_ledger import (
    LedgerAttempt,
    ResultLedger,
    ResultLedgerError,
    apply_result as apply_result_transition,
    register_accepted as register_accepted_transition,
)
from backend.apps.competition.domain.scoring import (
    FinalTiePolicy,
    ScoredAttempt,
    ScoreRules,
    Verdict,
    calculate_match_score,
)
from backend.apps.competition.models import (
    AcceptedAttempt,
    AttemptResult,
    Match,
    MatchRun,
    MatchSlot,
)
from backend.apps.events.models import MatchEvent
from backend.apps.events.services import append_event


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
    participants = tuple(
        UUID(str(value))
        for value in run.match.slots.filter(participant__isnull=False)
        .order_by("slot_index")
        .values_list("participant__user_id", flat=True)
    )
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


@transaction.atomic
def reconcile_match_run_deadline(
    run_id: UUID | str,
    *,
    now: datetime | None = None,
) -> MatchRun:
    """Close submissions at deadline and settle only after accepted work drains."""
    try:
        normalized_run_id = UUID(str(run_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise LedgerPersistenceError("run ID must be a UUID") from error
    run = _claim_run(normalized_run_id)
    Match.objects.filter(pk=run.match_id).update(updated_at=models.F("updated_at"))
    match = Match.objects.get(pk=run.match_id)
    if match.current_run_id != run.pk:
        raise LedgerPersistenceError("only the current run can reconcile its deadline")
    instant = now or timezone.now()
    try:
        clock = reconcile_deadline(
            ClockSnapshot(
                status=run.status,
                allowed_duration_ms=run.allowed_duration_ms,
                started_at=run.started_at,
                paused_at=run.paused_at,
                accumulated_pause_ms=run.accumulated_pause_ms,
            ),
            instant,
        )
    except ValueError as error:
        raise LedgerPersistenceError(str(error)) from error
    if clock.status.value == run.status:
        return run

    run.status = MatchRun.Status.FINALIZING
    run.revision += 1
    run.save(update_fields=("status", "revision"))
    match.status = Match.Status.FINALIZING
    match.save(update_fields=("status", "updated_at"))

    ledger = _ledger(run)
    if not ledger.pending_submission_ids:
        score = _calculate_score(ledger)
        run.score_snapshot = _score_payload(score)
        run.revision += 1
        run.save(update_fields=("score_snapshot", "revision"))
        _settle_finalizing_run(run, score, now=instant)
        _append_score_event(run, score)
    run.refresh_from_db()
    return run


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


def _public_score_payload(run: MatchRun, score) -> dict:
    users = {
        str(user.pk): user.display_name
        for user in User.objects.filter(pk__in=[item.user_id for item in score.participants])
    }
    labels = {
        item["problemId"]: item["label"]
        for item in run.problem_versions
    }
    return {
        "leaderUserId": score.winner_user_id,
        "players": [
            {
                "userId": participant.user_id,
                "displayName": users[participant.user_id],
                "solvedCount": participant.solved_count,
                "penaltyMs": participant.penalty_ms,
                "lastAcceptedElapsedMs": participant.last_accepted_elapsed_ms,
                "tasks": [
                    {
                        "problemId": problem.problem_id,
                        "label": labels[problem.problem_id],
                        "status": problem.outcome.value,
                        "attempts": problem.attempts,
                        "lastVerdict": problem.last_verdict.value if problem.last_verdict else None,
                    }
                    for problem in participant.problems
                ],
            }
            for participant in score.participants
        ],
    }


def _append_score_event(run: MatchRun, score) -> None:
    append_event(
        tournament_id=run.match.tournament_id,
        match_id=run.match_id,
        run_id=run.pk,
        event_type=MatchEvent.Types.SCORE_CHANGED,
        public_payload=_public_score_payload(run, score),
    )


def _advance_winner(match: Match, winner_user_id: str) -> None:
    if match.next_match_id is None or match.next_slot is None:
        return
    winner_entry = MatchSlot.objects.get(
        match=match,
        resolution=MatchSlot.Resolution.PLAYER,
        participant__user_id=winner_user_id,
    ).participant
    updated = MatchSlot.objects.filter(
        match_id=match.next_match_id,
        slot_index=match.next_slot,
        upstream_match=match,
        resolution=MatchSlot.Resolution.WAITING,
        participant__isnull=True,
    ).update(participant=winner_entry, resolution=MatchSlot.Resolution.PLAYER)
    if updated != 1:
        raise LedgerPersistenceError("downstream slot is no longer available for winner advancement")


def _settle_finalizing_run(run: MatchRun, score, *, now: datetime) -> None:
    """Finish a drained current run and publish its final score atomically."""
    match = Match.objects.select_related("tournament").get(pk=run.match_id)
    if match.current_run_id != run.pk or run.status != MatchRun.Status.FINALIZING:
        return
    if score.tied:
        run.status = MatchRun.Status.TIED
        match.status = Match.Status.TIED
        match.winner = None
        run.winner = None
    else:
        run.status = MatchRun.Status.FINISHED
        match.status = Match.Status.FINISHED
        winner_entry = MatchSlot.objects.get(
            match=match,
            resolution=MatchSlot.Resolution.PLAYER,
            participant__user_id=score.winner_user_id,
        ).participant
        run.winner = winner_entry
        match.winner = winner_entry
        _advance_winner(match, score.winner_user_id)
    run.finished_at = now
    run.revision += 1
    run.save(update_fields=("status", "winner", "finished_at", "revision"))
    match.save(update_fields=("status", "winner", "updated_at"))


def _calculate_score(ledger: ResultLedger):
    results = tuple(
        ScoredAttempt(
            submission_id=str(attempt.result.submission_id),
            run_id=str(attempt.result.run_id),
            user_id=str(attempt.result.user_id),
            problem_id=str(attempt.result.problem_id),
            received_at=attempt.result.received_at,
            elapsed_ms=attempt.result.elapsed_ms,
            verdict=attempt.result.verdict,
        )
        for attempt in ledger.attempts
        if attempt.result is not None
    )
    return calculate_match_score(
        run_id=str(ledger.run_id),
        participant_user_ids=tuple(map(str, ledger.participant_user_ids)),
        problem_ids=tuple(map(str, ledger.problem_ids)),
        results=results,
        rules=ledger.rules,
    )


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
        _append_score_event(run, transition.score)
        if run.status == MatchRun.Status.FINALIZING and transition.can_finalize:
            _settle_finalizing_run(run, transition.score, now=timezone.now())
    return transition.application.applied

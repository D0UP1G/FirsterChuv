"""Durable adapter for the pure accepted/result ledger transitions."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from functools import wraps
from uuid import UUID

from django.db import IntegrityError, OperationalError, connection, models, transaction
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.common.contracts import (
    AttemptReceipt,
    InfrastructureFailureReceipt,
    ResultReceipt,
)
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
    InfrastructureFailureRecord,
    Match,
    MatchRun,
    MatchSlot,
)
from backend.apps.events.models import MatchEvent
from backend.apps.events.services import (
    PublicSnapshotBusy,
    append_event,
    save_snapshot,
)


class LedgerPersistenceError(RuntimeError):
    """The persisted receipt cannot be admitted or applied safely."""

    status_code = 409
    code = "ledger_conflict"


class LedgerPersistenceBusy(LedgerPersistenceError):
    """A short-lived SQLite write collision exhausted bounded retries."""

    status_code = 503
    code = "ledger_busy"


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


def _retry_sqlite_transaction(function):
    """Retry the full ledger transaction; leave unrelated DB failures visible."""

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
                    raise LedgerPersistenceBusy(
                        "База занята; повторите обработку результата позже."
                    ) from error
                time.sleep(0.01 * (attempt + 1))
            except PublicSnapshotBusy as error:
                # A nested snapshot write cannot safely retry only its
                # savepoint: replay the accepted-result transaction so event
                # and snapshot remain one atomic state transition.
                if attempt == 2:
                    raise LedgerPersistenceBusy(
                        "База занята; повторите обработку результата позже."
                    ) from error
                time.sleep(0.01 * (attempt + 1))

    return wrapped


INFRA_FAILURE_REASON_CODES = frozenset(
    {
        "infrastructure_error",
        "judge_infrastructure_error",
        "judge_result_invalid",
        "worker_lease_expired",
    }
)


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


@_retry_sqlite_transaction
def register_accepted(receipt: AttemptReceipt) -> AcceptedAttempt:
    """Persist admission before returning success; exact retries are no-ops."""
    if not isinstance(receipt, AttemptReceipt):
        raise LedgerPersistenceError("accepted receipt has an invalid type")
    for field_name in ("submission_id", "run_id", "user_id", "problem_id"):
        if not isinstance(getattr(receipt, field_name), UUID):
            raise LedgerPersistenceError(f"accepted receipt {field_name} must be a UUID")

    # Reserve the run writer before any receipt lookup; concurrent DEFERRED
    # transactions must not both establish a read snapshot before upgrading it.
    run = _claim_run(receipt.run_id)
    existing = AcceptedAttempt.objects.filter(pk=receipt.submission_id).first()
    if existing is not None:
        if _receipt_matches(existing, receipt):
            return existing
        raise LedgerPersistenceError("submission_id already has a conflicting accepted receipt")

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


@_retry_sqlite_transaction
def record_infrastructure_failure(
    receipt: InfrastructureFailureReceipt,
) -> InfrastructureFailureRecord:
    """Persist one allowlisted failure without inventing a contestant verdict."""
    if not isinstance(receipt, InfrastructureFailureReceipt):
        raise LedgerPersistenceError("infrastructure failure receipt has an invalid type")
    for field_name in ("submission_id", "run_id"):
        if not isinstance(getattr(receipt, field_name), UUID):
            raise LedgerPersistenceError(f"failure receipt {field_name} must be a UUID")
    if (
        not isinstance(receipt.reason_code, str)
        or receipt.reason_code not in INFRA_FAILURE_REASON_CODES
    ):
        raise LedgerPersistenceError("infrastructure failure reason code is not allowlisted")
    if type(receipt.retryable) is not bool:
        raise LedgerPersistenceError("infrastructure failure retryable must be a boolean")

    run = _claim_run(receipt.run_id)
    accepted = (
        AcceptedAttempt.objects.filter(pk=receipt.submission_id)
        .select_related("run")
        .first()
    )
    if accepted is None or accepted.run_id != run.pk:
        raise LedgerPersistenceError("infrastructure failure has no matching accepted receipt")
    if hasattr(accepted, "result"):
        raise LedgerPersistenceError("a completed verdict cannot be replaced by infrastructure failure")

    existing = InfrastructureFailureRecord.objects.filter(accepted=accepted).first()
    if existing is not None:
        if (
            existing.reason_code == receipt.reason_code
            and existing.retryable == receipt.retryable
        ):
            return existing
        raise LedgerPersistenceError("submission_id already has a conflicting infrastructure failure")

    failure = InfrastructureFailureRecord.objects.create(
        accepted=accepted,
        reason_code=receipt.reason_code,
        retryable=receipt.retryable,
    )
    if run.match.current_run_id == run.pk:
        ledger = _ledger(run)
        if run.status == MatchRun.Status.FINALIZING:
            _continue_finalization(run, ledger, now=timezone.now())
        else:
            failures = _unresolved_infrastructure_failures(run.pk)
            _save_failure_snapshot(
                run,
                ledger,
                failures,
                resolution_required=any(not item.retryable for item in failures),
            )
    return failure


@_retry_sqlite_transaction
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
        return run
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
    _continue_finalization(run, ledger, now=instant)
    run.refresh_from_db()
    return run


def _unresolved_infrastructure_failures(run_id: UUID) -> list[InfrastructureFailureRecord]:
    return list(
        InfrastructureFailureRecord.objects.filter(
            accepted__run_id=run_id,
            resolved_at__isnull=True,
        ).select_related("accepted").order_by("accepted__received_at", "accepted_id")
    )


def _failure_payload(failures: list[InfrastructureFailureRecord]) -> list[dict]:
    return [
        {
            "reasonCode": failure.reason_code,
            "retryable": failure.retryable,
        }
        for failure in failures
    ]


def _continue_finalization(
    run: MatchRun,
    ledger: ResultLedger,
    *,
    now: datetime,
    publish_final_score: bool = True,
) -> None:
    """Drain results, but keep terminal infrastructure failures out of scoring."""
    failures = _unresolved_infrastructure_failures(run.pk)
    terminal_ids = {
        failure.accepted_id for failure in failures if not failure.retryable
    }
    pending_ids = set(ledger.pending_submission_ids)
    unresolved_ids = pending_ids - terminal_ids

    if unresolved_ids:
        if failures:
            _save_failure_snapshot(run, ledger, failures, resolution_required=bool(terminal_ids))
        return
    if terminal_ids:
        _save_failure_snapshot(run, ledger, failures, resolution_required=True)
        return

    score = _calculate_score(ledger)
    failures = _unresolved_infrastructure_failures(run.pk)
    score_payload = _score_payload(score)
    score_payload["resolutionRequired"] = any(not item.retryable for item in failures)
    score_payload["infrastructureFailures"] = _failure_payload(failures)
    run.score_snapshot = score_payload
    run.revision += 1
    run.save(update_fields=("score_snapshot", "revision"))
    _settle_finalizing_run(run, score, now=now)
    if publish_final_score:
        _append_score_event(run, score)


def _save_failure_snapshot(
    run: MatchRun,
    ledger: ResultLedger,
    failures: list[InfrastructureFailureRecord],
    *,
    resolution_required: bool,
) -> None:
    snapshot = _score_payload(_calculate_score(ledger))
    snapshot["winnerUserId"] = None
    snapshot["resolutionRequired"] = resolution_required
    snapshot["infrastructureFailures"] = _failure_payload(failures)
    run.score_snapshot = snapshot
    run.revision += 1
    run.save(update_fields=("score_snapshot", "revision"))


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
    payload = _public_score_payload(run, score)
    event_id = append_event(
        tournament_id=run.match.tournament_id,
        match_id=run.match_id,
        run_id=run.pk,
        event_type=MatchEvent.Types.SCORE_CHANGED,
        public_payload=payload,
    )
    save_snapshot(
        match_id=run.match_id,
        run_id=run.pk,
        last_event_id=event_id,
        public_payload=payload,
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


@_retry_sqlite_transaction
def apply_result(receipt: ResultReceipt) -> bool:
    """Durably record one verdict and atomically refresh only the current run score."""
    if not isinstance(receipt, ResultReceipt):
        raise LedgerPersistenceError("result receipt has an invalid type")
    for field_name in ("submission_id", "run_id", "user_id", "problem_id"):
        if not isinstance(getattr(receipt, field_name), UUID):
            raise LedgerPersistenceError(f"result receipt {field_name} must be a UUID")

    # Result delivery also reserves the run before reading its accepted receipt.
    run = _claim_run(receipt.run_id)
    Match.objects.filter(pk=run.match_id).update(updated_at=models.F("updated_at"))
    run.match.refresh_from_db()
    accepted = AcceptedAttempt.objects.filter(pk=receipt.submission_id).first()
    if accepted is None:
        raise LedgerPersistenceError("result has no accepted receipt")
    if accepted.run_id != run.pk:
        raise LedgerPersistenceError("result run differs from its accepted receipt")
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
    InfrastructureFailureRecord.objects.filter(
        accepted=accepted,
        resolved_at__isnull=True,
    ).update(resolved_at=timezone.now())
    if transition.application.applied and transition.score is not None:
        failures = _unresolved_infrastructure_failures(run.pk)
        score_payload = _score_payload(transition.score)
        score_payload["resolutionRequired"] = any(not item.retryable for item in failures)
        score_payload["infrastructureFailures"] = _failure_payload(failures)
        run.score_snapshot = score_payload
        run.revision += 1
        run.save(update_fields=("score_snapshot", "revision"))
        _append_score_event(run, transition.score)
        if run.status == MatchRun.Status.FINALIZING:
            current_run_id = Match.objects.filter(pk=run.match_id).values_list(
                "current_run_id", flat=True
            ).first()
            if current_run_id == run.pk:
                _continue_finalization(
                    run,
                    _ledger(run),
                    now=timezone.now(),
                    publish_final_score=False,
                )
    return transition.application.applied

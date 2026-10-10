"""Durable orchestration for trusted submission and result workers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from threading import Event, Thread
from typing import Callable, Protocol

from backend.apps.common.contracts import JudgeInfrastructureError, JudgeResult

from .errors import IntegrationUnavailable, StaleLease, SubmissionError
from .models import Submission
from .ports import InfrastructureFailureSink, ResultSink
from .services import (
    MAX_LEASE_SECONDS,
    LeasedSubmission,
    SubmissionService,
)


class SubmissionExecutor(Protocol):
    """Resolve trusted immutable task data and run one leased submission."""

    def execute(self, submission: LeasedSubmission) -> JudgeResult: ...


class WorkerAction(str, Enum):
    IDLE = "idle"
    SUBMISSION_FINISHED = "submission_finished"
    SUBMISSION_RETRY_SCHEDULED = "submission_retry_scheduled"
    SUBMISSION_INFRA_FAILED = "submission_infra_failed"
    RESULT_DELIVERED = "result_delivered"
    RESULT_RETRY_SCHEDULED = "result_retry_scheduled"
    FAILURE_DELIVERED = "failure_delivered"
    FAILURE_RETRY_SCHEDULED = "failure_retry_scheduled"
    STALE_LEASE = "stale_lease"


@dataclass(frozen=True, slots=True)
class WorkerIteration:
    action: WorkerAction

    @property
    def did_work(self) -> bool:
        return self.action is not WorkerAction.IDLE


class _LeaseHeartbeat:
    """Keep a long-running claim alive without holding a DB transaction."""

    def __init__(self, service: SubmissionService, claim: LeasedSubmission, lease_seconds: int) -> None:
        self.service = service
        self.claim = claim
        self.lease_seconds = lease_seconds
        self.interval_seconds = max(0.1, min(lease_seconds / 3, 30.0))
        self.stop_event = Event()
        self.thread = Thread(target=self._run, name="submission-lease-heartbeat", daemon=True)

    def __enter__(self) -> _LeaseHeartbeat:
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop_event.set()
        self.thread.join()

    def _run(self) -> None:
        from django.db import close_old_connections

        while not self.stop_event.wait(self.interval_seconds):
            close_old_connections()
            try:
                self.service.renew_claim(self.claim, lease_seconds=self.lease_seconds)
            except Exception:
                # The final transition is still guarded by the persisted lease token
                # and expiry. If renewal cannot be confirmed, never force a verdict.
                return
            finally:
                close_old_connections()


class SubmissionWorker:
    """Process one durable queue item at a time through required runtime ports."""

    def __init__(
        self,
        *,
        service: SubmissionService | None,
        executor: SubmissionExecutor | None,
        result_sink: ResultSink | None,
        failure_sink: InfrastructureFailureSink | None,
        recovery_hook: Callable[[], object] | None = None,
    ) -> None:
        if service is None or executor is None or result_sink is None or failure_sink is None:
            raise IntegrationUnavailable(
                "submission worker requires a queue service, trusted executor, real ResultSink, "
                "and InfrastructureFailureSink"
            )
        if not isinstance(service, SubmissionService):
            raise TypeError("submission worker service must be SubmissionService")
        if not callable(getattr(executor, "execute", None)):
            raise TypeError("submission worker executor must provide execute()")
        if not callable(getattr(result_sink, "apply_result", None)):
            raise TypeError("submission worker result sink must provide apply_result()")
        if not callable(getattr(failure_sink, "record_infrastructure_failure", None)):
            raise TypeError("submission worker failure sink must provide record_infrastructure_failure()")
        self.service = service
        self.executor = executor
        self.result_sink = result_sink
        self.failure_sink = failure_sink
        self.recovery_hook = recovery_hook

    def run_once(
        self,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> WorkerIteration:
        """Deliver one due outbox item or execute one accepted submission.

        The queue service recovers expired submission leases before making a new
        claim; the result service similarly releases expired delivery leases.
        """
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or not 0 < lease_seconds <= MAX_LEASE_SECONDS
        ):
            raise ValueError("worker lease must be a positive bounded integer")

        if self.recovery_hook is not None:
            self.recovery_hook()

        delivery = self.service.claim_pending_result(now=now, lease_seconds=lease_seconds)
        if delivery is not None:
            try:
                delivered = self.service.deliver_result(
                    delivery,
                    sink=self.result_sink,
                    now=now,
                )
            except StaleLease:
                return WorkerIteration(WorkerAction.STALE_LEASE)
            action = WorkerAction.RESULT_DELIVERED if delivered else WorkerAction.RESULT_RETRY_SCHEDULED
            return WorkerIteration(action)

        failure_delivery = self.service.claim_pending_infrastructure_failure(
            now=now,
            lease_seconds=lease_seconds,
        )
        if failure_delivery is not None:
            try:
                delivered = self.service.deliver_infrastructure_failure(
                    failure_delivery,
                    sink=self.failure_sink,
                    now=now,
                )
            except StaleLease:
                return WorkerIteration(WorkerAction.STALE_LEASE)
            action = WorkerAction.FAILURE_DELIVERED if delivered else WorkerAction.FAILURE_RETRY_SCHEDULED
            return WorkerIteration(action)

        claim = self.service.claim_next(now=now, lease_seconds=lease_seconds)
        if claim is None:
            return WorkerIteration(WorkerAction.IDLE)

        try:
            with _LeaseHeartbeat(self.service, claim, lease_seconds):
                result = self.executor.execute(claim)
        except JudgeInfrastructureError:
            return self._record_infrastructure_failure(claim, "judge_infrastructure_error", now=now)

        if not isinstance(result, JudgeResult):
            return self._record_infrastructure_failure(claim, "judge_result_invalid", now=now)

        try:
            self.service.complete_claim(
                claim,
                verdict=result.verdict,
                compile_diagnostics=result.compile_diagnostics,
                metrics=result.metrics,
                internal_reason=result.internal_reason,
                now=now,
            )
        except StaleLease:
            return WorkerIteration(WorkerAction.STALE_LEASE)
        except SubmissionError:
            return self._record_infrastructure_failure(claim, "judge_result_invalid", now=now)
        return WorkerIteration(WorkerAction.SUBMISSION_FINISHED)

    def _record_infrastructure_failure(
        self,
        claim: LeasedSubmission,
        error_code: str,
        *,
        now: datetime | None,
    ) -> WorkerIteration:
        try:
            status = self.service.record_infrastructure_failure(
                claim,
                error_code=error_code,
                now=now,
            )
        except StaleLease:
            return WorkerIteration(WorkerAction.STALE_LEASE)
        action = (
            WorkerAction.SUBMISSION_INFRA_FAILED
            if status == Submission.Status.INFRA_FAILED
            else WorkerAction.SUBMISSION_RETRY_SCHEDULED
        )
        return WorkerIteration(action)

"""Production LocalJudge execution and trusted submission worker wiring."""

from __future__ import annotations

import re
import threading
import time

from django.db import Error as DjangoDatabaseError

from backend.apps.common.contracts import (
    JudgeInfrastructureError,
    JudgeResult,
    RunProblemSnapshot,
    RunProblemSnapshotProvider,
    TrustedJudgeJob,
)
from backend.apps.competition.gateway import (
    CompetitionSnapshotUnavailable,
    get_competition_gateway,
    get_run_problem_snapshot_provider,
)
from backend.apps.judge.provider import LocalJudge
from backend.apps.judge.runner import DockerRunner, SandboxClaim, cleanup_orphaned_claim_containers
from backend.apps.problems.catalog import DjangoProblemCatalog

from .adapters import InfrastructureFailureSinkAdapter, ResultSinkAdapter
from .services import LeasedSubmission, SubmissionService
from .worker import SubmissionWorker


class LocalJudgeSubmissionExecutor:
    """Resolve the immutable run assignment, then invoke the real LocalJudge."""

    def __init__(self, snapshot_provider: RunProblemSnapshotProvider) -> None:
        if not callable(getattr(snapshot_provider, "resolve", None)):
            raise TypeError("run problem snapshot provider must provide resolve()")
        self.snapshot_provider = snapshot_provider

    def execute(self, submission: LeasedSubmission) -> JudgeResult:
        try:
            snapshot = self.snapshot_provider.resolve(submission.run_id, submission.problem_id)
        except (CompetitionSnapshotUnavailable, DjangoDatabaseError) as error:
            raise JudgeInfrastructureError("run_problem_snapshot_unavailable") from error
        if not isinstance(snapshot, RunProblemSnapshot):
            raise JudgeInfrastructureError("run_problem_snapshot_invalid")
        if (
            snapshot.run_id != submission.run_id
            or snapshot.problem_id != submission.problem_id
            or not isinstance(snapshot.problem_version, str)
            or not snapshot.problem_version
            or not isinstance(snapshot.problem_checksum, str)
            or re.fullmatch(r"[0-9a-f]{64}", snapshot.problem_checksum) is None
        ):
            raise JudgeInfrastructureError("run_problem_snapshot_invalid")

        job = TrustedJudgeJob(
            submission_id=submission.submission_id,
            source=submission.source,
            language_id=submission.language_id,
            problem_id=submission.problem_id,
            problem_version=snapshot.problem_version,
            problem_checksum=snapshot.problem_checksum,
        )
        judge = LocalJudge(
            DjangoProblemCatalog(),
            sandbox=DockerRunner(
                claim=SandboxClaim(
                    submission_id=submission.submission_id,
                    lease_token=submission.lease_token,
                )
            ),
        )
        return judge.execute(job)


class SandboxContainerRecovery:
    """Retry lease-aware orphan cleanup periodically as leases expire after restart."""

    def __init__(self, *, interval_seconds: float = 10.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("sandbox recovery interval must be positive")
        self.interval_seconds = interval_seconds
        self._last_run: float | None = None
        self._lock = threading.Lock()

    def __call__(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_run is not None and now - self._last_run < self.interval_seconds:
                return
            recover_orphan_sandbox_containers()
            self._last_run = now


def build_submission_worker() -> SubmissionWorker:
    """Build the worker exclusively from real production providers."""
    gateway = get_competition_gateway()
    snapshot_provider = get_run_problem_snapshot_provider()

    # A worker's queue transitions do not admit new work; admission stays separately
    # wired through the API service and its real gateway/event/language providers.
    service = SubmissionService(competition=None, event_writer=None, language_registry=None)
    return SubmissionWorker(
        service=service,
        executor=LocalJudgeSubmissionExecutor(snapshot_provider),
        result_sink=ResultSinkAdapter(gateway),
        failure_sink=InfrastructureFailureSinkAdapter(gateway),
        recovery_hook=SandboxContainerRecovery(),
    )


def recover_orphan_sandbox_containers() -> int:
    """Remove worker containers only after their exact durable lease has ended."""
    return cleanup_orphaned_claim_containers()

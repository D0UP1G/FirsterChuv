from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from backend.apps.common.contracts import (
    JudgeInfrastructureError,
    JudgeResult,
    RunProblemSnapshot,
)
from backend.apps.competition.gateway import CompetitionSnapshotUnavailable
from backend.apps.submissions.runtime import (
    LocalJudgeSubmissionExecutor,
    SandboxContainerRecovery,
    build_submission_worker,
)
from backend.apps.submissions.services import LeasedSubmission
from backend.apps.submissions.worker import SubmissionWorker


class FakeSnapshotProvider:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.requested = []

    def resolve(self, run_id, problem_id):
        self.requested.append((run_id, problem_id))
        if isinstance(self.snapshot, Exception):
            raise self.snapshot
        return self.snapshot


class LocalJudgeSubmissionExecutorTests(TestCase):
    def setUp(self):
        self.claim = LeasedSubmission(
            submission_id=uuid4(),
            lease_token=uuid4(),
            user_id=uuid4(),
            match_id=uuid4(),
            run_id=uuid4(),
            problem_id=uuid4(),
            language_id="cpp20",
            source="int main() { return 0; }",
            received_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
            elapsed_ms=2000,
            scoring_version="score-v1",
            attempt_count=1,
            lease_until=datetime(2026, 10, 10, 0, 1, tzinfo=timezone.utc),
        )

    @patch("backend.apps.submissions.runtime.LocalJudge")
    def test_resolves_exact_run_snapshot_and_builds_claim_owned_judge(self, judge_type):
        snapshot = RunProblemSnapshot(
            run_id=self.claim.run_id,
            problem_id=self.claim.problem_id,
            problem_version="v7",
            problem_checksum="a" * 64,
        )
        provider = FakeSnapshotProvider(snapshot)
        judge = judge_type.return_value
        judge.execute.return_value = JudgeResult(verdict="OK")

        result = LocalJudgeSubmissionExecutor(provider).execute(self.claim)

        self.assertEqual(result, JudgeResult(verdict="OK"))
        self.assertEqual(provider.requested, [(self.claim.run_id, self.claim.problem_id)])
        job = judge.execute.call_args.args[0]
        self.assertEqual(job.problem_version, "v7")
        self.assertEqual(job.problem_checksum, "a" * 64)
        self.assertEqual(job.source, self.claim.source)
        sandbox = judge_type.call_args.kwargs["sandbox"]
        self.assertEqual(sandbox._claim.submission_id, self.claim.submission_id)
        self.assertEqual(sandbox._claim.lease_token, self.claim.lease_token)

    def test_rejects_mismatched_or_malformed_run_snapshot(self):
        provider = FakeSnapshotProvider(
            RunProblemSnapshot(
                run_id=uuid4(),
                problem_id=self.claim.problem_id,
                problem_version="v7",
                problem_checksum="a" * 64,
            )
        )
        with self.assertRaises(JudgeInfrastructureError):
            LocalJudgeSubmissionExecutor(provider).execute(self.claim)

    def test_snapshot_unavailable_is_an_infrastructure_failure(self):
        provider = FakeSnapshotProvider(CompetitionSnapshotUnavailable())

        with self.assertRaisesRegex(JudgeInfrastructureError, "run_problem_snapshot_unavailable"):
            LocalJudgeSubmissionExecutor(provider).execute(self.claim)

    @patch("backend.apps.submissions.runtime.get_run_problem_snapshot_provider")
    @patch("backend.apps.submissions.runtime.get_competition_gateway")
    def test_worker_factory_uses_real_gateway_adapters_and_snapshot_provider(self, get_gateway, get_snapshot_provider):
        gateway = get_gateway.return_value
        get_snapshot_provider.return_value = FakeSnapshotProvider(None)

        worker = build_submission_worker()

        self.assertIsInstance(worker, SubmissionWorker)
        self.assertIs(worker.result_sink.gateway, gateway)
        self.assertIs(worker.failure_sink.gateway, gateway)
        self.assertIsNone(worker.service.competition)
        self.assertTrue(callable(worker.recovery_hook))

    @patch("backend.apps.submissions.runtime.recover_orphan_sandbox_containers")
    @patch("backend.apps.submissions.runtime.time.monotonic", side_effect=(100.0, 105.0, 111.0))
    def test_sandbox_recovery_rechecks_when_lease_may_have_expired(self, _monotonic, recover):
        recovery = SandboxContainerRecovery(interval_seconds=10)

        recovery()
        recovery()
        recovery()

        self.assertEqual(recover.call_count, 2)

from datetime import timedelta
from time import sleep
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command, CommandError
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.common.contracts import JudgeInfrastructureError, JudgeResult, ResultApplication
from backend.apps.submissions.adapters import ResultSinkAdapter
from backend.apps.submissions.errors import IntegrationUnavailable
from backend.apps.submissions.factory import get_submission_worker
from backend.apps.submissions.models import QueueCounter, ResultOutbox, Submission
from backend.apps.submissions.ports import SubmissionPermit
from backend.apps.submissions.services import SubmissionService
from backend.apps.submissions.worker import SubmissionWorker, WorkerAction


class FakeCompetition:
    def authorize_submission(self, actor_id, match_id, run_id, problem_id, received_at):
        return SubmissionPermit(run_id=run_id, elapsed_ms=25, scoring_version="score-v1")

    def register_accepted(self, receipt):
        pass


class FakeEventWriter:
    def append(self, scope, event_type, public_payload):
        return 1


class FakeLanguageRegistry:
    def is_supported(self, language_id):
        return language_id == "cpp20"


class FakeExecutor:
    def __init__(self, result=None, error=None, on_execute=None):
        self.result = result or JudgeResult(verdict="OK", metrics={"wallMs": 5})
        self.error = error
        self.on_execute = on_execute
        self.submissions = []

    def execute(self, submission):
        self.submissions.append(submission)
        if self.on_execute is not None:
            self.on_execute(submission)
        if self.error is not None:
            raise self.error
        return self.result


class FakeResultSink:
    def __init__(self):
        self.receipts = []

    def apply_result(self, receipt):
        self.receipts.append(receipt)
        return True


class SubmissionWorkerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user("worker-author@example.test", "Author", "passphrase")
        self.match_id = uuid4()
        self.run_id = uuid4()
        self.problem_id = uuid4()
        self.now = timezone.now()
        self.service = SubmissionService(
            competition=FakeCompetition(),
            event_writer=FakeEventWriter(),
            language_registry=FakeLanguageRegistry(),
        )
        self.executor = FakeExecutor()
        self.sink = FakeResultSink()
        self.worker = SubmissionWorker(
            service=self.service,
            executor=self.executor,
            result_sink=self.sink,
        )

    def submit(self, key="attempt", source="int main() { return 0; }"):
        return self.service.admit(
            actor_id=self.user.pk,
            match_id=self.match_id,
            run_id=self.run_id,
            problem_id=self.problem_id,
            language_id="cpp20",
            source=source,
            idempotency_key=key,
            received_at=self.now,
        )

    def test_worker_finishes_submission_then_delivers_durable_outbox(self):
        accepted = self.submit()

        executed = self.worker.run_once(now=self.now + timedelta(seconds=1))

        record = Submission.objects.get(pk=accepted.id)
        self.assertEqual(executed.action, WorkerAction.SUBMISSION_FINISHED)
        self.assertEqual(record.status, Submission.Status.FINISHED)
        self.assertEqual(record.verdict, Submission.Verdict.OK)
        self.assertEqual(ResultOutbox.objects.get(submission=record).status, ResultOutbox.Status.PENDING)
        self.assertEqual(self.executor.submissions[0].source, "int main() { return 0; }")
        self.assertEqual(self.sink.receipts, [])

        delivered = self.worker.run_once(now=self.now + timedelta(seconds=2))

        self.assertEqual(delivered.action, WorkerAction.RESULT_DELIVERED)
        self.assertEqual(len(self.sink.receipts), 1)
        self.assertEqual(ResultOutbox.objects.get(submission=record).status, ResultOutbox.Status.SENT)

    def test_due_result_is_delivered_before_claiming_another_submission(self):
        first = self.submit(key="first")
        second = self.submit(key="second")
        self.worker.run_once(now=self.now + timedelta(seconds=1))

        delivery = self.worker.run_once(now=self.now + timedelta(seconds=2))

        self.assertEqual(delivery.action, WorkerAction.RESULT_DELIVERED)
        self.assertEqual(len(self.executor.submissions), 1)
        self.assertEqual(Submission.objects.get(pk=second.id).status, Submission.Status.QUEUED)
        self.assertEqual(Submission.objects.get(pk=first.id).status, Submission.Status.FINISHED)

    def test_superseded_result_application_is_successful_outbox_delivery(self):
        class SupersededGateway:
            def apply_result(self, receipt):
                return ResultApplication(applied=False)

        accepted = self.submit()
        self.worker.run_once(now=self.now + timedelta(seconds=1))
        result_worker = SubmissionWorker(
            service=self.service,
            executor=self.executor,
            result_sink=ResultSinkAdapter(SupersededGateway()),
        )

        iteration = result_worker.run_once(now=self.now + timedelta(seconds=2))

        self.assertEqual(iteration.action, WorkerAction.RESULT_DELIVERED)
        self.assertEqual(ResultOutbox.objects.get(submission_id=accepted.id).status, ResultOutbox.Status.SENT)

    def test_typed_judge_infrastructure_error_retries_without_verdict(self):
        accepted = self.submit()
        self.worker.executor = FakeExecutor(error=JudgeInfrastructureError("private diagnostic"))

        iteration = self.worker.run_once(now=self.now + timedelta(seconds=1))

        record = Submission.objects.get(pk=accepted.id)
        self.assertEqual(iteration.action, WorkerAction.SUBMISSION_RETRY_SCHEDULED)
        self.assertEqual(record.status, Submission.Status.RETRY_WAIT)
        self.assertIsNone(record.verdict)
        self.assertEqual(record.internal_reason, "judge_infrastructure_error")
        self.assertEqual(QueueCounter.objects.get(scope_key="global").pending_count, 1)

    def test_invalid_provider_result_is_recorded_as_infrastructure_error(self):
        accepted = self.submit()
        self.worker.executor = FakeExecutor(result=JudgeResult(verdict="FAKE"))

        iteration = self.worker.run_once(now=self.now + timedelta(seconds=1))

        record = Submission.objects.get(pk=accepted.id)
        self.assertEqual(iteration.action, WorkerAction.SUBMISSION_RETRY_SCHEDULED)
        self.assertEqual(record.status, Submission.Status.RETRY_WAIT)
        self.assertIsNone(record.verdict)
        self.assertEqual(record.internal_reason, "judge_result_invalid")

    def test_stale_worker_result_is_discarded_after_lease_recovery(self):
        accepted = self.submit()

        def expire_lease(_submission):
            SubmissionService.recover_expired_claims(now=self.now + timedelta(seconds=5))

        self.worker.executor = FakeExecutor(on_execute=expire_lease)
        iteration = self.worker.run_once(now=self.now + timedelta(seconds=1), lease_seconds=1)

        record = Submission.objects.get(pk=accepted.id)
        self.assertEqual(iteration.action, WorkerAction.STALE_LEASE)
        self.assertEqual(record.status, Submission.Status.RETRY_WAIT)
        self.assertIsNone(record.verdict)

    def test_heartbeat_renews_lease_during_long_execution(self):
        accepted = self.submit()
        self.worker.executor = FakeExecutor(on_execute=lambda _submission: sleep(1.3))

        iteration = self.worker.run_once(lease_seconds=1)

        record = Submission.objects.get(pk=accepted.id)
        self.assertEqual(iteration.action, WorkerAction.SUBMISSION_FINISHED)
        self.assertEqual(record.status, Submission.Status.FINISHED)
        self.assertEqual(record.verdict, Submission.Verdict.OK)

    def test_idle_worker_recovers_expired_claim_after_restart(self):
        accepted = self.submit()
        claim = SubmissionService.claim_next(now=self.now + timedelta(seconds=1), lease_seconds=1)
        later = self.now + timedelta(seconds=5)

        iteration = self.worker.run_once(now=later)

        record = Submission.objects.get(pk=accepted.id)
        self.assertEqual(iteration.action, WorkerAction.IDLE)
        self.assertEqual(record.status, Submission.Status.RETRY_WAIT)
        self.assertEqual(QueueCounter.objects.get(scope_key="global").pending_count, 1)
        self.assertIsNotNone(claim)

    def test_expired_outbox_lease_is_reclaimed_and_delivered(self):
        accepted = self.submit()
        self.worker.run_once(now=self.now + timedelta(seconds=1))
        outbox = ResultOutbox.objects.get(submission_id=accepted.id)
        outbox.status = ResultOutbox.Status.SENDING
        outbox.lease_token = uuid4()
        outbox.lease_until = self.now + timedelta(seconds=2)
        outbox.save(update_fields=("status", "lease_token", "lease_until"))

        iteration = self.worker.run_once(now=self.now + timedelta(seconds=3))

        self.assertEqual(iteration.action, WorkerAction.RESULT_DELIVERED)
        self.assertEqual(ResultOutbox.objects.get(pk=outbox.pk).status, ResultOutbox.Status.SENT)
        self.assertEqual(len(self.sink.receipts), 1)

    def test_missing_runtime_worker_factory_fails_closed(self):
        with override_settings(SUBMISSION_WORKER_FACTORY=None):
            with self.assertRaises(IntegrationUnavailable):
                get_submission_worker()
            with self.assertRaises(CommandError):
                call_command("run_judge_worker", "--once")

    def test_command_redacts_unexpected_worker_exception(self):
        class FailingWorker:
            def run_once(self, **kwargs):
                raise RuntimeError("private execution diagnostic")

        with patch(
            "backend.apps.submissions.management.commands.run_judge_worker.get_submission_worker",
            return_value=FailingWorker(),
        ):
            with self.assertRaises(CommandError) as error:
                call_command("run_judge_worker", "--once")

        self.assertIn("unexpected internal failure", str(error.exception))
        self.assertNotIn("private execution diagnostic", str(error.exception))

    def test_command_redacts_runtime_factory_exception(self):
        with patch(
            "backend.apps.submissions.management.commands.run_judge_worker.get_submission_worker",
            side_effect=RuntimeError("private factory diagnostic"),
        ):
            with self.assertRaises(CommandError) as error:
                call_command("run_judge_worker", "--once")

        self.assertIn("runtime factory failed", str(error.exception))
        self.assertNotIn("private factory diagnostic", str(error.exception))

    def test_worker_rejects_missing_runtime_ports_and_invalid_lease(self):
        with self.assertRaises(IntegrationUnavailable):
            SubmissionWorker(service=self.service, executor=self.executor, result_sink=None)
        with self.assertRaises(ValueError):
            self.worker.run_once(lease_seconds=0)

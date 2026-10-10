from datetime import datetime, timezone
from unittest import TestCase
from uuid import uuid4

from backend.apps.common.contracts import (
    AttemptReceipt as CommonAttemptReceipt,
    InfrastructureFailureReceipt as CommonInfrastructureFailureReceipt,
    ResultApplication,
    ResultReceipt as CommonResultReceipt,
    SubmissionPermit as CommonSubmissionPermit,
)
from backend.apps.submissions.adapters import (
    CompetitionGatewayAdapter,
    EventWriterAdapter,
    InfrastructureFailureSinkAdapter,
    LanguageRegistryAdapter,
    ResultSinkAdapter,
)
from backend.apps.submissions.errors import IntegrationUnavailable
from backend.apps.submissions.ports import (
    AttemptReceipt,
    InfrastructureFailureReceipt,
    ResultReceipt,
    SubmissionPermit,
)


class FakeCompetitionGateway:
    def __init__(self, *, applied=True):
        self.authorized = []
        self.accepted = []
        self.results = []
        self.failures = []
        self.applied = applied

    def authorize_submission(self, actor_id, match_id, run_id, problem_id, received_at):
        self.authorized.append((actor_id, match_id, run_id, problem_id, received_at))
        return CommonSubmissionPermit(run_id=run_id, elapsed_ms=42, scoring_version="score-v1")

    def register_accepted(self, receipt):
        self.accepted.append(receipt)

    def apply_result(self, receipt):
        self.results.append(receipt)
        return ResultApplication(applied=self.applied)

    def record_infrastructure_failure(self, receipt):
        self.failures.append(receipt)


class FakeEventWriter:
    def __init__(self):
        self.events = []

    def append(self, scope, event_type, public_payload):
        self.events.append((scope, event_type, public_payload))
        return 17


class FakeLanguageRegistry:
    def __init__(self, supported):
        self.supported = set(supported)
        self.queried = []

    def is_supported(self, language_id):
        self.queried.append(language_id)
        return language_id in self.supported


class SubmissionAdapterTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
        self.submission_id = uuid4()
        self.user_id = uuid4()
        self.match_id = uuid4()
        self.run_id = uuid4()
        self.problem_id = uuid4()

    def test_competition_adapter_maps_permit_and_omits_local_match_id(self):
        gateway = FakeCompetitionGateway()
        adapter = CompetitionGatewayAdapter(gateway)

        permit = adapter.authorize_submission(
            self.user_id,
            self.match_id,
            self.run_id,
            self.problem_id,
            self.now,
        )
        local_receipt = AttemptReceipt(
            submission_id=self.submission_id,
            user_id=self.user_id,
            match_id=self.match_id,
            run_id=self.run_id,
            problem_id=self.problem_id,
            received_at=self.now,
            elapsed_ms=42,
            scoring_version="score-v1",
        )
        adapter.register_accepted(local_receipt)

        self.assertEqual(permit, SubmissionPermit(self.run_id, 42, "score-v1"))
        self.assertEqual(gateway.authorized, [(self.user_id, self.match_id, self.run_id, self.problem_id, self.now)])
        self.assertEqual(len(gateway.accepted), 1)
        self.assertIsInstance(gateway.accepted[0], CommonAttemptReceipt)
        self.assertEqual(gateway.accepted[0].submission_id, self.submission_id)
        self.assertFalse(hasattr(gateway.accepted[0], "match_id"))

    def test_result_adapter_maps_common_receipt_and_preserves_applied_false(self):
        for applied in (True, False):
            with self.subTest(applied=applied):
                gateway = FakeCompetitionGateway(applied=applied)
                adapter = ResultSinkAdapter(gateway)
                local_receipt = ResultReceipt(
                    submission_id=self.submission_id,
                    user_id=self.user_id,
                    match_id=self.match_id,
                    run_id=self.run_id,
                    problem_id=self.problem_id,
                    received_at=self.now,
                    elapsed_ms=42,
                    scoring_version="score-v1",
                    verdict="OK",
                )

                delivered_application = adapter.apply_result(local_receipt)

                self.assertEqual(delivered_application, applied)
                self.assertEqual(len(gateway.results), 1)
                self.assertIsInstance(gateway.results[0], CommonResultReceipt)
                self.assertEqual(gateway.results[0].run_id, self.run_id)
                self.assertFalse(hasattr(gateway.results[0], "match_id"))

    def test_event_and_language_adapters_delegate_without_runtime_defaults(self):
        writer = FakeEventWriter()
        languages = FakeLanguageRegistry(("cpp20",))
        event_adapter = EventWriterAdapter(writer)
        language_adapter = LanguageRegistryAdapter(languages)
        payload = {"submissionId": str(self.submission_id)}

        event_id = event_adapter.append("match", "submission.accepted", payload)

        self.assertEqual(event_id, 17)
        self.assertEqual(writer.events, [("match", "submission.accepted", payload)])
        self.assertTrue(language_adapter.is_supported("cpp20"))
        self.assertFalse(language_adapter.is_supported("unknown"))
        self.assertEqual(languages.queried, ["cpp20", "unknown"])

    def test_infrastructure_failure_adapter_forwards_allowlisted_receipt(self):
        gateway = FakeCompetitionGateway()
        adapter = InfrastructureFailureSinkAdapter(gateway)
        receipt = InfrastructureFailureReceipt(
            submission_id=self.submission_id,
            run_id=self.run_id,
            reason_code="worker_lease_expired",
            retryable=False,
        )

        adapter.record_infrastructure_failure(receipt)

        self.assertEqual(
            gateway.failures,
            [CommonInfrastructureFailureReceipt(
                submission_id=self.submission_id,
                run_id=self.run_id,
                reason_code="worker_lease_expired",
                retryable=False,
            )],
        )

    def test_missing_or_malformed_production_ports_fail_closed(self):
        with self.assertRaises(IntegrationUnavailable):
            CompetitionGatewayAdapter(None)
        with self.assertRaises(IntegrationUnavailable):
            ResultSinkAdapter(None)
        with self.assertRaises(IntegrationUnavailable):
            InfrastructureFailureSinkAdapter(None)
        with self.assertRaises(IntegrationUnavailable):
            EventWriterAdapter(None)
        with self.assertRaises(IntegrationUnavailable):
            LanguageRegistryAdapter(None)
        with self.assertRaises(TypeError):
            CompetitionGatewayAdapter(object())
        with self.assertRaises(TypeError):
            ResultSinkAdapter(object())

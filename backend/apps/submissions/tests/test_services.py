from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.submissions.errors import (
    IdempotencyConflict,
    IntegrationUnavailable,
    QueueFull,
    StaleLease,
    SubmissionError,
    SubmissionNotFound,
)
from backend.apps.submissions.models import QueueCounter, ResultOutbox, Submission
from backend.apps.submissions.ports import ResultReceipt, SubmissionPermit
from backend.apps.submissions.services import SubmissionService


class FakeCompetition:
    """Test-only stand-in for the A2 transaction-bound gateway."""

    def __init__(self):
        self.authorized = []
        self.accepted = []
        self.permit = None

    def authorize_submission(self, actor_id, match_id, run_id, problem_id, received_at):
        self.authorized.append((actor_id, match_id, run_id, problem_id, received_at))
        return self.permit or SubmissionPermit(run_id=run_id, elapsed_ms=37, scoring_version="score-v1")

    def register_accepted(self, receipt):
        self.accepted.append(receipt)


class FakeEventWriter:
    """Test-only event adapter; assertions ensure source never enters its payload."""

    def __init__(self, *, fail=False):
        self.events = []
        self.fail = fail

    def append(self, scope, event_type, public_payload):
        if self.fail:
            raise RuntimeError("event store unavailable")
        self.events.append((scope, event_type, public_payload))
        return len(self.events)


class FakeLanguageRegistry:
    def __init__(self, supported=("cpp20",)):
        self.supported = set(supported)

    def is_supported(self, language_id):
        return language_id in self.supported


class FakeResultSink:
    """Test-only idempotent sink substitute; production has no default sink."""

    def __init__(self, *, fail_once=False):
        self.fail_once = fail_once
        self.receipts: list[ResultReceipt] = []

    def apply_result(self, receipt):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("result store unavailable")
        self.receipts.append(receipt)
        return True


class SubmissionQueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("author@example.test", "Author", "passphrase")
        self.other_user = User.objects.create_user("other@example.test", "Other", "passphrase")
        self.match_id = uuid4()
        self.run_id = uuid4()
        self.problem_id = uuid4()
        self.now = timezone.now()
        self.competition = FakeCompetition()
        self.events = FakeEventWriter()
        self.languages = FakeLanguageRegistry()
        self.service = self.make_service()

    def make_service(self, **overrides):
        settings = {
            "competition": self.competition,
            "event_writer": self.events,
            "language_registry": self.languages,
            **overrides,
        }
        return SubmissionService(**settings)

    def submit(self, *, user=None, key="attempt-1", source="int main() { return 0; }", service=None):
        return (service or self.service).admit(
            actor_id=(user or self.user).pk,
            match_id=self.match_id,
            run_id=self.run_id,
            problem_id=self.problem_id,
            language_id="cpp20",
            source=source,
            idempotency_key=key,
            received_at=self.now,
        )

    def test_admission_is_idempotent_and_public_metadata_omits_source(self):
        accepted = self.submit()
        repeated = self.submit()
        self.assertEqual(accepted.id, repeated.id)
        self.assertEqual(accepted.elapsed_ms, 37)
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(len(self.competition.authorized), 1)
        self.assertEqual(len(self.competition.accepted), 1)
        self.assertEqual(len(self.events.events), 1)
        self.assertNotIn("source", self.events.events[0][2])
        self.assertNotIn("source", {field.name for field in accepted.__dataclass_fields__.values()})

    def test_reusing_an_idempotency_key_for_changed_body_is_conflict(self):
        self.submit()
        with self.assertRaises(IdempotencyConflict):
            self.submit(source="int main() { return 1; }")

    def test_missing_runtime_ports_fail_closed_without_persisting_source(self):
        service = self.make_service(competition=None, event_writer=None, language_registry=None)
        with self.assertRaises(IntegrationUnavailable):
            self.submit(service=service)
        self.assertEqual(Submission.objects.count(), 0)
        self.assertEqual(QueueCounter.objects.count(), 0)

    def test_unsupported_language_source_cap_and_invalid_verdict_are_rejected(self):
        self.languages.supported.clear()
        with self.assertRaises(SubmissionError):
            self.submit()
        self.languages.supported.add("cpp20")
        with self.assertRaises(SubmissionError):
            self.submit(source="x" * (32 * 1024 + 1))
        with self.assertRaises(SubmissionError):
            self.service.complete_claim(None, verdict="INFRASTRUCTURE_ERROR")

    def test_event_failure_rolls_back_source_and_capacity_reservation(self):
        self.events.fail = True
        with self.assertRaises(RuntimeError):
            self.submit()
        self.assertEqual(Submission.objects.count(), 0)
        self.assertEqual(QueueCounter.objects.count(), 0)

    def test_only_author_can_read_source_or_private_diagnostics(self):
        accepted = self.submit()
        self.assertEqual(
            SubmissionService.get_source_for_author(actor_id=self.user.pk, submission_id=accepted.id),
            "int main() { return 0; }",
        )
        with self.assertRaises(SubmissionNotFound):
            SubmissionService.get_source_for_author(actor_id=self.other_user.pk, submission_id=accepted.id)
        with self.assertRaises(SubmissionNotFound):
            SubmissionService.get_author_metadata(actor_id=self.other_user.pk, submission_id=accepted.id)

    def test_bounded_queue_releases_capacity_only_after_terminal_result(self):
        limited = self.make_service(max_pending_global=1, max_pending_per_user=1)
        accepted = self.submit(service=limited)
        with self.assertRaises(QueueFull):
            self.submit(service=limited, key="attempt-2")
        claim = SubmissionService.claim_next(now=self.now + timedelta(seconds=1), lease_seconds=30)
        self.assertIsNotNone(claim)
        SubmissionService.complete_claim(claim, verdict="OK", now=self.now + timedelta(seconds=2))
        self.assertEqual(QueueCounter.objects.get(scope_key="global").pending_count, 0)
        self.assertEqual(QueueCounter.objects.get(scope_key=f"actor:{self.user.pk}").pending_count, 0)
        second = self.submit(service=limited, key="attempt-2")
        self.assertNotEqual(accepted.id, second.id)

    def test_match_queue_capacity_is_bounded_and_released_after_terminal_result(self):
        limited = self.make_service(max_pending_per_match=1, max_pending_global=5, max_pending_per_user=5)
        accepted = self.submit(service=limited, user=self.user)
        with self.assertRaises(QueueFull):
            self.submit(service=limited, user=self.other_user, key="other-match-attempt")
        self.assertEqual(QueueCounter.objects.get(scope_key=f"match:{self.match_id}").pending_count, 1)

        claim = SubmissionService.claim_next(now=self.now + timedelta(seconds=1), lease_seconds=30)
        SubmissionService.complete_claim(claim, verdict="WA", now=self.now + timedelta(seconds=2))
        self.assertEqual(QueueCounter.objects.get(scope_key=f"match:{self.match_id}").pending_count, 0)
        second = self.submit(service=limited, user=self.other_user, key="other-match-attempt")
        self.assertNotEqual(accepted.id, second.id)

    def test_expired_lease_retries_and_old_worker_cannot_finish_new_claim(self):
        accepted = self.submit()
        first_claim_time = self.now + timedelta(seconds=1)
        old_claim = SubmissionService.claim_next(now=first_claim_time, lease_seconds=1)
        self.assertEqual(old_claim.submission_id, accepted.id)
        retry_time = first_claim_time + timedelta(seconds=3)
        self.assertEqual(SubmissionService.recover_expired_claims(now=retry_time), 1)
        self.assertEqual(Submission.objects.get(pk=accepted.id).status, Submission.Status.RETRY_WAIT)
        new_claim = SubmissionService.claim_next(now=retry_time + timedelta(seconds=2), lease_seconds=30)
        self.assertEqual(new_claim.attempt_count, 2)
        with self.assertRaises(StaleLease):
            SubmissionService.complete_claim(old_claim, verdict="OK", now=retry_time + timedelta(seconds=3))
        receipt = SubmissionService.complete_claim(
            new_claim,
            verdict="WA",
            now=retry_time + timedelta(seconds=3),
        )
        self.assertEqual(receipt.received_at, self.now)
        self.assertEqual(receipt.elapsed_ms, 37)

    def test_current_worker_can_renew_a_live_bounded_lease(self):
        self.submit()
        claim = SubmissionService.claim_next(now=self.now + timedelta(seconds=1), lease_seconds=5)
        renewed_until = SubmissionService.renew_claim(
            claim,
            now=self.now + timedelta(seconds=3),
            lease_seconds=20,
        )
        record = Submission.objects.get(pk=claim.submission_id)
        self.assertEqual(renewed_until, self.now + timedelta(seconds=23))
        self.assertEqual(record.lease_until, renewed_until)
        shorter_renewal = SubmissionService.renew_claim(
            claim,
            now=self.now + timedelta(seconds=4),
            lease_seconds=1,
        )
        self.assertEqual(shorter_renewal, renewed_until)

    def test_infrastructure_retries_end_without_fabricating_a_verdict(self):
        accepted = self.submit()
        now = self.now + timedelta(seconds=1)
        for attempt in range(1, 6):
            claim = SubmissionService.claim_next(now=now, lease_seconds=60)
            self.assertIsNotNone(claim)
            state = SubmissionService.record_infrastructure_failure(
                claim,
                error_code="docker_unavailable",
                now=now + timedelta(milliseconds=1),
            )
            self.assertEqual(claim.attempt_count, attempt)
            if attempt < 5:
                self.assertEqual(state, Submission.Status.RETRY_WAIT)
                now = now + timedelta(seconds=2 ** (attempt - 1) + 2)
        record = Submission.objects.get(pk=accepted.id)
        self.assertEqual(record.status, Submission.Status.INFRA_FAILED)
        self.assertIsNone(record.verdict)
        self.assertEqual(QueueCounter.objects.get(scope_key="global").pending_count, 0)

    def test_result_outbox_survives_sink_failure_and_delivers_idempotent_receipt(self):
        self.submit()
        claim = SubmissionService.claim_next(now=self.now + timedelta(seconds=1), lease_seconds=30)
        completed_at = self.now + timedelta(seconds=2)
        receipt = SubmissionService.complete_claim(
            claim,
            verdict="CE",
            compile_diagnostics="compiler detail",
            metrics={"compileMs": 4},
            now=completed_at,
        )
        self.assertEqual(ResultOutbox.objects.get().status, ResultOutbox.Status.PENDING)
        delivery_time = completed_at + timedelta(seconds=1)
        first_delivery = SubmissionService.claim_pending_result(now=delivery_time, lease_seconds=30)
        self.assertEqual(first_delivery.receipt, receipt)
        sink = FakeResultSink(fail_once=True)
        self.assertFalse(SubmissionService.deliver_result(first_delivery, sink=sink, now=delivery_time))
        self.assertEqual(ResultOutbox.objects.get().status, ResultOutbox.Status.PENDING)

        second_delivery = SubmissionService.claim_pending_result(
            now=delivery_time + timedelta(seconds=2),
            lease_seconds=30,
        )
        self.assertTrue(SubmissionService.deliver_result(second_delivery, sink=sink, now=delivery_time + timedelta(seconds=2)))
        self.assertEqual(sink.receipts, [receipt])
        self.assertEqual(ResultOutbox.objects.get().status, ResultOutbox.Status.SENT)
        self.assertIsNone(SubmissionService.claim_pending_result(now=delivery_time + timedelta(seconds=3)))

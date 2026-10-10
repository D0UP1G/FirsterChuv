"""SQLite-backed submission admission, worker leases, and durable result delivery."""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import sleep
from uuid import UUID, uuid4

from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import Case, DateTimeField, F, Value, When
from django.utils import timezone

from .errors import (
    AdmissionBusy,
    IdempotencyConflict,
    IntegrationUnavailable,
    QueueFull,
    StaleLease,
    SubmissionError,
    SubmissionNotFound,
)
from .models import InfrastructureFailureOutbox, QueueCounter, ResultOutbox, Submission
from .ports import (
    AttemptReceipt,
    CompetitionGatewayV1,
    EventWriter,
    InfrastructureFailureReceipt,
    InfrastructureFailureSink,
    LanguageRegistry,
    ResultReceipt,
    ResultSink,
)

MAX_SOURCE_BYTES = 32 * 1024
MAX_IDEMPOTENCY_KEY_BYTES = 128
MAX_DIAGNOSTICS_BYTES = 8 * 1024
MAX_METRIC_COUNT = 32
MAX_LEASE_SECONDS = 15 * 60
MAX_RETRY_ATTEMPTS = 5
MAX_CLAIM_COLLISIONS = 8
MAX_ADMISSION_ATTEMPTS = 3
ADMISSION_RETRY_DELAYS = (0.025, 0.075)
MAX_MATCH_PARTICIPANTS = 2
SUPPORTED_VERDICTS = frozenset(Submission.Verdict.values)
LANGUAGE_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
INFRA_FAILURE_REASON_CODES = frozenset(
    {
        "infrastructure_error",
        "judge_infrastructure_error",
        "judge_result_invalid",
        "worker_lease_expired",
    }
)


@dataclass(frozen=True, slots=True)
class SubmissionMetadata:
    id: UUID
    user_id: UUID
    match_id: UUID
    run_id: UUID
    problem_id: UUID
    language_id: str
    received_at: datetime
    elapsed_ms: int
    status: str
    verdict: str | None
    attempt_count: int


@dataclass(frozen=True, slots=True)
class AuthorSubmissionResult:
    submission: SubmissionMetadata
    compile_diagnostics: str | None


@dataclass(frozen=True, slots=True)
class LeasedSubmission:
    submission_id: UUID
    lease_token: UUID
    user_id: UUID
    match_id: UUID
    run_id: UUID
    problem_id: UUID
    language_id: str
    source: str
    received_at: datetime
    elapsed_ms: int
    scoring_version: str
    attempt_count: int
    lease_until: datetime


@dataclass(frozen=True, slots=True)
class ResultDeliveryClaim:
    outbox_id: int
    lease_token: UUID
    receipt: ResultReceipt
    attempt_count: int


@dataclass(frozen=True, slots=True)
class FailureDeliveryClaim:
    outbox_id: int
    lease_token: UUID
    receipt: InfrastructureFailureReceipt
    attempt_count: int


def _digest_parts(*parts: str | bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        encoded = part if isinstance(part, bytes) else part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _idempotency_digest(key: str) -> str:
    if not isinstance(key, str):
        raise SubmissionError("idempotency key is required")
    try:
        encoded = key.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise SubmissionError("idempotency key is invalid") from error
    if not encoded or len(encoded) > MAX_IDEMPOTENCY_KEY_BYTES:
        raise SubmissionError("idempotency key is missing or too long")
    return hashlib.sha256(encoded).hexdigest()


def _source_bytes(source: str, max_source_bytes: int) -> bytes:
    if not isinstance(source, str):
        raise SubmissionError("source must be text")
    try:
        encoded = source.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise SubmissionError("source is not valid UTF-8 text") from error
    if not encoded or len(encoded) > max_source_bytes:
        raise SubmissionError("source is empty or exceeds the configured limit")
    return encoded


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


def _retry_admission_after_lock(error: OperationalError, attempt: int) -> bool:
    if not _is_sqlite_lock_error(error):
        return False
    if attempt + 1 >= MAX_ADMISSION_ATTEMPTS:
        raise AdmissionBusy("submission admission stayed busy after bounded retries") from error
    sleep(ADMISSION_RETRY_DELAYS[attempt])
    return True


def _metadata(record: Submission) -> SubmissionMetadata:
    return SubmissionMetadata(
        id=record.pk,
        user_id=record.actor_id,
        match_id=record.match_id,
        run_id=record.run_id,
        problem_id=record.problem_id,
        language_id=record.language_id,
        received_at=record.received_at,
        elapsed_ms=record.elapsed_ms,
        status=record.status,
        verdict=record.verdict,
        attempt_count=record.attempt_count,
    )


def _counter_key(scope: str, value: UUID | None = None) -> str:
    if scope == "global":
        return scope
    if value is None:
        raise ValueError("queue capacity scope requires an id")
    return f"{scope}:{value}"


def _acquire_admission_write_intent() -> None:
    # Start the transaction with a write, before its idempotency read. SQLite
    # shared-cache cannot reliably upgrade two concurrent read transactions
    # to writers on QueueCounter; a no-op insert serializes them instead.
    QueueCounter.objects.bulk_create(
        [QueueCounter(scope_key=_counter_key("global"))],
        ignore_conflicts=True,
    )


def _reserve_capacity(
    user_id: UUID,
    match_id: UUID,
    *,
    global_limit: int,
    user_limit: int,
    match_limit: int,
) -> None:
    for key, limit in (
        (_counter_key("global"), global_limit),
        (_counter_key("actor", user_id), user_limit),
        (_counter_key("match", match_id), match_limit),
    ):
        QueueCounter.objects.get_or_create(scope_key=key)
        updated = QueueCounter.objects.filter(scope_key=key, pending_count__lt=limit).update(
            pending_count=F("pending_count") + 1
        )
        if updated != 1:
            raise QueueFull("submission queue is full")


def _release_capacity(user_id: UUID, match_id: UUID) -> None:
    for key in (_counter_key("global"), _counter_key("actor", user_id), _counter_key("match", match_id)):
        updated = QueueCounter.objects.filter(scope_key=key, pending_count__gt=0).update(
            pending_count=F("pending_count") - 1
        )
        if updated != 1:
            raise RuntimeError("submission queue capacity counter is inconsistent")


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(60, 2 ** max(0, attempt_count - 1)))


def _result_receipt(record: Submission) -> ResultReceipt:
    if record.verdict not in SUPPORTED_VERDICTS:
        raise RuntimeError("finished submission has no valid verdict")
    return ResultReceipt(
        submission_id=record.pk,
        user_id=record.actor_id,
        match_id=record.match_id,
        run_id=record.run_id,
        problem_id=record.problem_id,
        received_at=record.received_at,
        elapsed_ms=record.elapsed_ms,
        scoring_version=record.scoring_version,
        verdict=record.verdict,
    )


def _infrastructure_failure_receipt(record: Submission) -> InfrastructureFailureReceipt:
    reason_code = (
        record.internal_reason
        if isinstance(record.internal_reason, str) and record.internal_reason in INFRA_FAILURE_REASON_CODES
        else "infrastructure_error"
    )
    return InfrastructureFailureReceipt(
        submission_id=record.pk,
        run_id=record.run_id,
        reason_code=reason_code,
        retryable=False,
    )


class SubmissionService:
    def __init__(
        self,
        *,
        competition: CompetitionGatewayV1 | None,
        event_writer: EventWriter | None,
        language_registry: LanguageRegistry | None,
        max_pending_global: int = 1000,
        max_pending_per_user: int = 10,
        max_pending_per_match: int | None = None,
        max_source_bytes: int = MAX_SOURCE_BYTES,
    ) -> None:
        if max_pending_per_match is None:
            max_pending_per_match = MAX_MATCH_PARTICIPANTS * max_pending_per_user
        limits = (max_pending_global, max_pending_per_user, max_pending_per_match, max_source_bytes)
        if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in limits):
            raise ValueError("submission service limits must be positive")
        if max_source_bytes > MAX_SOURCE_BYTES:
            raise ValueError("source limit cannot exceed the sandbox source cap")
        self.competition = competition
        self.event_writer = event_writer
        self.language_registry = language_registry
        self.max_pending_global = max_pending_global
        self.max_pending_per_user = max_pending_per_user
        self.max_pending_per_match = max_pending_per_match
        self.max_source_bytes = max_source_bytes

    def _require_admission_ports(self) -> tuple[CompetitionGatewayV1, EventWriter, LanguageRegistry]:
        if self.competition is None or self.event_writer is None or self.language_registry is None:
            raise IntegrationUnavailable("submission admission is unavailable without real competition, event, and language ports")
        return self.competition, self.event_writer, self.language_registry

    def admit(
        self,
        *,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        language_id: str,
        source: str,
        idempotency_key: str,
        received_at: datetime | None = None,
    ) -> SubmissionMetadata:
        key_digest = _idempotency_digest(idempotency_key)
        source_bytes = _source_bytes(source, self.max_source_bytes)
        if not isinstance(language_id, str) or not LANGUAGE_ID_RE.fullmatch(language_id):
            raise SubmissionError("language id is invalid")
        request_digest = _digest_parts(
            str(actor_id),
            str(match_id),
            str(run_id),
            str(problem_id),
            language_id,
            source_bytes,
        )
        accepted_at = received_at or timezone.now()
        if not timezone.is_aware(accepted_at):
            raise SubmissionError("received_at must be timezone-aware")

        def existing_idempotent_submission() -> SubmissionMetadata | None:
            existing = Submission.objects.filter(actor_id=actor_id, idempotency_sha256=key_digest).first()
            if existing is None:
                return None
            if existing.request_sha256 != request_digest:
                raise IdempotencyConflict("idempotency key was already used for another request")
            return _metadata(existing)

        def admit_once() -> SubmissionMetadata:
            existing = existing_idempotent_submission()
            if existing is not None:
                return existing

            competition, event_writer, language_registry = self._require_admission_ports()
            if not language_registry.is_supported(language_id):
                raise SubmissionError("language is not available")

            with transaction.atomic():
                _acquire_admission_write_intent()
                existing = existing_idempotent_submission()
                if existing is not None:
                    return existing

                _reserve_capacity(
                    actor_id,
                    match_id,
                    global_limit=self.max_pending_global,
                    user_limit=self.max_pending_per_user,
                    match_limit=self.max_pending_per_match,
                )
                permit = competition.authorize_submission(actor_id, match_id, run_id, problem_id, accepted_at)
                if (
                    permit.run_id != run_id
                    or not isinstance(permit.elapsed_ms, int)
                    or isinstance(permit.elapsed_ms, bool)
                    or not 0 <= permit.elapsed_ms <= 2**63 - 1
                    or not isinstance(permit.scoring_version, str)
                    or not permit.scoring_version
                    or len(permit.scoring_version) > 64
                ):
                    raise SubmissionError("competition gateway returned an invalid permit")
                record = Submission.objects.create(
                    actor_id=actor_id,
                    match_id=match_id,
                    run_id=run_id,
                    problem_id=problem_id,
                    language_id=language_id,
                    source=source,
                    source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                    request_sha256=request_digest,
                    idempotency_sha256=key_digest,
                    received_at=accepted_at,
                    elapsed_ms=permit.elapsed_ms,
                    scoring_version=permit.scoring_version,
                    status=Submission.Status.QUEUED,
                    available_at=accepted_at,
                )
                receipt = AttemptReceipt(
                    submission_id=record.pk,
                    user_id=actor_id,
                    match_id=match_id,
                    run_id=run_id,
                    problem_id=problem_id,
                    received_at=accepted_at,
                    elapsed_ms=permit.elapsed_ms,
                    scoring_version=permit.scoring_version,
                )
                # Production ports must use this process/database transaction; no network adapter is valid here.
                competition.register_accepted(receipt)
                event_writer.append(
                    f"match:{match_id}",
                    "submission.accepted",
                    {
                        "submissionId": str(record.pk),
                        "userId": str(actor_id),
                        "matchId": str(match_id),
                        "runId": str(run_id),
                        "problemId": str(problem_id),
                        "languageId": language_id,
                        "receivedAt": accepted_at.isoformat(),
                    },
                )
                return _metadata(record)

        for attempt in range(MAX_ADMISSION_ATTEMPTS):
            try:
                return admit_once()
            except IntegrityError:
                try:
                    existing = existing_idempotent_submission()
                except OperationalError as error:
                    if _retry_admission_after_lock(error, attempt):
                        continue
                    raise
                if existing is None:
                    raise
                return existing
            except OperationalError as error:
                if _retry_admission_after_lock(error, attempt):
                    continue
                raise

        raise AssertionError("bounded admission loop exited unexpectedly")

    @staticmethod
    def get_author_metadata(*, actor_id: UUID, submission_id: UUID) -> AuthorSubmissionResult:
        record = Submission.objects.filter(pk=submission_id, actor_id=actor_id).first()
        if record is None:
            raise SubmissionNotFound("submission not found")
        return AuthorSubmissionResult(_metadata(record), record.compile_diagnostics)

    @staticmethod
    def get_source_for_author(*, actor_id: UUID, submission_id: UUID) -> str:
        record = Submission.objects.filter(pk=submission_id, actor_id=actor_id).only("source").first()
        if record is None:
            raise SubmissionNotFound("submission not found")
        return record.source

    @staticmethod
    def list_for_author(
        *,
        actor_id: UUID,
        match_id: UUID,
        problem_id: UUID | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[SubmissionMetadata], int]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("submission pagination is out of range")
        records = Submission.objects.filter(actor_id=actor_id, match_id=match_id)
        if problem_id is not None:
            records = records.filter(problem_id=problem_id)
        count = records.count()
        page = records.order_by("-received_at", "-id")[offset : offset + limit]
        return [_metadata(record) for record in page], count

    @staticmethod
    def claim_next(*, now: datetime | None = None, lease_seconds: int = 60) -> LeasedSubmission | None:
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time) or not 0 < lease_seconds <= MAX_LEASE_SECONDS:
            raise ValueError("worker lease must be bounded and timezone-aware")
        SubmissionService.recover_expired_claims(now=current_time)
        for _ in range(MAX_CLAIM_COLLISIONS):
            candidate = (
                Submission.objects.filter(
                    status__in=(Submission.Status.QUEUED, Submission.Status.RETRY_WAIT),
                    available_at__lte=current_time,
                )
                .order_by("received_at", "created_at", "id")
                .values("id", "status")
                .first()
            )
            if candidate is None:
                return None
            token = uuid4()
            updated = Submission.objects.filter(
                pk=candidate["id"],
                status=candidate["status"],
                available_at__lte=current_time,
            ).update(
                status=Submission.Status.RUNNING,
                attempt_count=F("attempt_count") + 1,
                lease_token=token,
                lease_until=current_time + timedelta(seconds=lease_seconds),
                updated_at=current_time,
            )
            if updated == 0:
                continue
            record = Submission.objects.get(pk=candidate["id"], lease_token=token)
            return LeasedSubmission(
                submission_id=record.pk,
                lease_token=token,
                user_id=record.actor_id,
                match_id=record.match_id,
                run_id=record.run_id,
                problem_id=record.problem_id,
                language_id=record.language_id,
                source=record.source,
                received_at=record.received_at,
                elapsed_ms=record.elapsed_ms,
                scoring_version=record.scoring_version,
                attempt_count=record.attempt_count,
                lease_until=record.lease_until,
            )
        return None

    @staticmethod
    def renew_claim(
        claim: LeasedSubmission,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> datetime:
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time) or not 0 < lease_seconds <= MAX_LEASE_SECONDS:
            raise ValueError("worker lease renewal must be bounded and timezone-aware")
        requested_lease_until = current_time + timedelta(seconds=lease_seconds)
        updated = Submission.objects.filter(
            pk=claim.submission_id,
            status=Submission.Status.RUNNING,
            lease_token=claim.lease_token,
            lease_until__gt=current_time,
        ).update(
            lease_until=Case(
                When(lease_until__gt=requested_lease_until, then=F("lease_until")),
                default=Value(requested_lease_until),
                output_field=DateTimeField(),
            ),
            updated_at=current_time,
        )
        if updated != 1:
            raise StaleLease("worker lease is no longer current")
        return Submission.objects.values_list("lease_until", flat=True).get(
            pk=claim.submission_id,
            lease_token=claim.lease_token,
        )

    @staticmethod
    def recover_expired_claims(*, now: datetime | None = None) -> int:
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time):
            raise ValueError("recovery time must be timezone-aware")
        recovered = 0
        with transaction.atomic():
            expired = list(
                Submission.objects.filter(
                    status=Submission.Status.RUNNING,
                    lease_until__lte=current_time,
                ).values_list("id", "actor_id", "match_id", "attempt_count")
            )
            for submission_id, actor_id, match_id, attempts in expired:
                if attempts >= MAX_RETRY_ATTEMPTS:
                    updated = Submission.objects.filter(
                        pk=submission_id,
                        status=Submission.Status.RUNNING,
                        lease_until__lte=current_time,
                    ).update(
                        status=Submission.Status.INFRA_FAILED,
                        completed_at=current_time,
                        lease_token=None,
                        lease_until=None,
                        internal_reason="worker_lease_expired",
                        updated_at=current_time,
                    )
                    if updated:
                        _release_capacity(actor_id, match_id)
                        InfrastructureFailureOutbox.objects.get_or_create(
                            submission_id=submission_id,
                            defaults={"available_at": current_time},
                        )
                        recovered += 1
                else:
                    updated = Submission.objects.filter(
                        pk=submission_id,
                        status=Submission.Status.RUNNING,
                        lease_until__lte=current_time,
                    ).update(
                        status=Submission.Status.RETRY_WAIT,
                        available_at=current_time + _retry_delay(attempts),
                        lease_token=None,
                        lease_until=None,
                        internal_reason="worker_lease_expired",
                        updated_at=current_time,
                    )
                    recovered += bool(updated)
        return recovered

    @staticmethod
    def record_infrastructure_failure(
        claim: LeasedSubmission,
        *,
        error_code: str,
        now: datetime | None = None,
    ) -> str:
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time):
            raise ValueError("failure time must be timezone-aware")
        safe_code = error_code if isinstance(error_code, str) and error_code in INFRA_FAILURE_REASON_CODES else "infrastructure_error"
        with transaction.atomic():
            record = Submission.objects.filter(
                pk=claim.submission_id,
                status=Submission.Status.RUNNING,
                lease_token=claim.lease_token,
                lease_until__gt=current_time,
            ).first()
            if record is None:
                raise StaleLease("worker lease is no longer current")
            exhausted = record.attempt_count >= MAX_RETRY_ATTEMPTS
            new_status = Submission.Status.INFRA_FAILED if exhausted else Submission.Status.RETRY_WAIT
            updated = Submission.objects.filter(
                pk=record.pk,
                status=Submission.Status.RUNNING,
                lease_token=claim.lease_token,
            ).update(
                status=new_status,
                available_at=current_time if exhausted else current_time + _retry_delay(record.attempt_count),
                completed_at=current_time if exhausted else None,
                lease_token=None,
                lease_until=None,
                internal_reason=safe_code,
                updated_at=current_time,
            )
            if updated != 1:
                raise StaleLease("worker lease is no longer current")
            if exhausted:
                _release_capacity(record.actor_id, record.match_id)
                InfrastructureFailureOutbox.objects.get_or_create(
                    submission_id=record.pk,
                    defaults={"available_at": current_time},
                )
            return new_status

    @staticmethod
    def complete_claim(
        claim: LeasedSubmission,
        *,
        verdict: str,
        compile_diagnostics: str | None = None,
        metrics: Mapping[str, int | float] | None = None,
        internal_reason: str | None = None,
        now: datetime | None = None,
    ) -> ResultReceipt:
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time):
            raise ValueError("completion time must be timezone-aware")
        if not isinstance(verdict, str) or verdict not in SUPPORTED_VERDICTS:
            raise SubmissionError("judge result has an unsupported verdict")
        if compile_diagnostics is not None:
            if not isinstance(compile_diagnostics, str):
                raise SubmissionError("compile diagnostics must be text")
            try:
                diagnostics_size = len(compile_diagnostics.encode("utf-8", errors="strict"))
            except UnicodeEncodeError as error:
                raise SubmissionError("compile diagnostics are not valid UTF-8 text") from error
            if diagnostics_size > MAX_DIAGNOSTICS_BYTES:
                raise SubmissionError("compile diagnostics exceed their private size limit")
        if metrics is not None and not isinstance(metrics, Mapping):
            raise SubmissionError("judge metrics must be a mapping")
        normalized_metrics: dict[str, int | float] = {}
        for key, value in (metrics or {}).items():
            if (
                not isinstance(key, str)
                or not key
                or len(key) > 64
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (isinstance(value, int) and abs(value) > 2**63 - 1)
                or (isinstance(value, float) and not math.isfinite(value))
            ):
                raise SubmissionError("judge metrics are invalid")
            normalized_metrics[key] = value
            if len(normalized_metrics) > MAX_METRIC_COUNT:
                raise SubmissionError("judge metrics exceed their count limit")
        if internal_reason is not None and (
            not isinstance(internal_reason, str) or len(internal_reason) > 128
        ):
            raise SubmissionError("internal result reason is too long")

        with transaction.atomic():
            record = Submission.objects.filter(
                pk=claim.submission_id,
                status=Submission.Status.RUNNING,
                lease_token=claim.lease_token,
                lease_until__gt=current_time,
            ).first()
            if record is None:
                raise StaleLease("worker lease is no longer current")
            updated = Submission.objects.filter(
                pk=record.pk,
                status=Submission.Status.RUNNING,
                lease_token=claim.lease_token,
                lease_until__gt=current_time,
            ).update(
                status=Submission.Status.FINISHED,
                verdict=verdict,
                compile_diagnostics=compile_diagnostics,
                metrics=normalized_metrics,
                internal_reason=internal_reason,
                completed_at=current_time,
                lease_token=None,
                lease_until=None,
                updated_at=current_time,
            )
            if updated != 1:
                raise StaleLease("worker lease is no longer current")
            record.verdict = verdict
            receipt = _result_receipt(record)
            ResultOutbox.objects.create(submission=record, available_at=current_time)
            _release_capacity(record.actor_id, record.match_id)
            return receipt

    @staticmethod
    def claim_pending_result(
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> ResultDeliveryClaim | None:
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time) or not 0 < lease_seconds <= MAX_LEASE_SECONDS:
            raise ValueError("result lease must be bounded and timezone-aware")
        with transaction.atomic():
            ResultOutbox.objects.filter(
                status=ResultOutbox.Status.SENDING,
                lease_until__lte=current_time,
            ).update(
                status=ResultOutbox.Status.PENDING,
                lease_token=None,
                lease_until=None,
                available_at=current_time,
            )
            for _ in range(MAX_CLAIM_COLLISIONS):
                outbox = (
                    ResultOutbox.objects.filter(
                        status=ResultOutbox.Status.PENDING,
                        available_at__lte=current_time,
                    )
                    .order_by("created_at", "id")
                    .select_related("submission")
                    .first()
                )
                if outbox is None:
                    return None
                token = uuid4()
                updated = ResultOutbox.objects.filter(
                    pk=outbox.pk,
                    status=ResultOutbox.Status.PENDING,
                    available_at__lte=current_time,
                ).update(
                    status=ResultOutbox.Status.SENDING,
                    attempt_count=F("attempt_count") + 1,
                    lease_token=token,
                    lease_until=current_time + timedelta(seconds=lease_seconds),
                )
                if updated == 0:
                    continue
                submission = outbox.submission
                receipt = _result_receipt(submission)
                return ResultDeliveryClaim(outbox.pk, token, receipt, outbox.attempt_count + 1)
        return None

    @staticmethod
    def deliver_result(
        claim: ResultDeliveryClaim,
        *,
        sink: ResultSink | None,
        now: datetime | None = None,
    ) -> bool:
        if sink is None:
            raise IntegrationUnavailable("result delivery requires a real ResultSink")
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time):
            raise ValueError("result delivery time must be timezone-aware")
        outbox = ResultOutbox.objects.filter(
            pk=claim.outbox_id,
            status=ResultOutbox.Status.SENDING,
            lease_token=claim.lease_token,
            lease_until__gt=current_time,
        ).first()
        if outbox is None:
            raise StaleLease("result delivery lease is no longer current")
        try:
            sink.apply_result(claim.receipt)
        except Exception:
            retry_at = current_time + _retry_delay(claim.attempt_count)
            updated = ResultOutbox.objects.filter(
                pk=claim.outbox_id,
                status=ResultOutbox.Status.SENDING,
                lease_token=claim.lease_token,
            ).update(
                status=ResultOutbox.Status.PENDING,
                available_at=retry_at,
                lease_token=None,
                lease_until=None,
                last_error_code="result_sink_failed",
            )
            if updated != 1:
                raise StaleLease("result delivery lease is no longer current")
            return False
        updated = ResultOutbox.objects.filter(
            pk=claim.outbox_id,
            status=ResultOutbox.Status.SENDING,
            lease_token=claim.lease_token,
            lease_until__gt=current_time,
        ).update(
            status=ResultOutbox.Status.SENT,
            sent_at=current_time,
            lease_token=None,
            lease_until=None,
            last_error_code=None,
        )
        if updated != 1:
            raise StaleLease("result delivery lease is no longer current")
        return True

    @staticmethod
    def claim_pending_infrastructure_failure(
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> FailureDeliveryClaim | None:
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time) or not 0 < lease_seconds <= MAX_LEASE_SECONDS:
            raise ValueError("failure delivery lease must be bounded and timezone-aware")
        with transaction.atomic():
            InfrastructureFailureOutbox.objects.filter(
                status=InfrastructureFailureOutbox.Status.SENDING,
                lease_until__lte=current_time,
            ).update(
                status=InfrastructureFailureOutbox.Status.PENDING,
                lease_token=None,
                lease_until=None,
                available_at=current_time,
            )
            for _ in range(MAX_CLAIM_COLLISIONS):
                outbox = (
                    InfrastructureFailureOutbox.objects.filter(
                        status=InfrastructureFailureOutbox.Status.PENDING,
                        available_at__lte=current_time,
                    )
                    .order_by("created_at", "id")
                    .select_related("submission")
                    .first()
                )
                if outbox is None:
                    return None
                token = uuid4()
                updated = InfrastructureFailureOutbox.objects.filter(
                    pk=outbox.pk,
                    status=InfrastructureFailureOutbox.Status.PENDING,
                    available_at__lte=current_time,
                ).update(
                    status=InfrastructureFailureOutbox.Status.SENDING,
                    attempt_count=F("attempt_count") + 1,
                    lease_token=token,
                    lease_until=current_time + timedelta(seconds=lease_seconds),
                )
                if updated == 0:
                    continue
                return FailureDeliveryClaim(
                    outbox_id=outbox.pk,
                    lease_token=token,
                    receipt=_infrastructure_failure_receipt(outbox.submission),
                    attempt_count=outbox.attempt_count + 1,
                )
        return None

    @staticmethod
    def deliver_infrastructure_failure(
        claim: FailureDeliveryClaim,
        *,
        sink: InfrastructureFailureSink | None,
        now: datetime | None = None,
    ) -> bool:
        if sink is None:
            raise IntegrationUnavailable("failure delivery requires a real InfrastructureFailureSink")
        current_time = now or timezone.now()
        if not timezone.is_aware(current_time):
            raise ValueError("failure delivery time must be timezone-aware")
        outbox = InfrastructureFailureOutbox.objects.filter(
            pk=claim.outbox_id,
            status=InfrastructureFailureOutbox.Status.SENDING,
            lease_token=claim.lease_token,
            lease_until__gt=current_time,
        ).first()
        if outbox is None:
            raise StaleLease("failure delivery lease is no longer current")
        try:
            sink.record_infrastructure_failure(claim.receipt)
        except Exception:
            retry_at = current_time + _retry_delay(claim.attempt_count)
            updated = InfrastructureFailureOutbox.objects.filter(
                pk=claim.outbox_id,
                status=InfrastructureFailureOutbox.Status.SENDING,
                lease_token=claim.lease_token,
            ).update(
                status=InfrastructureFailureOutbox.Status.PENDING,
                available_at=retry_at,
                lease_token=None,
                lease_until=None,
                last_error_code="failure_sink_failed",
            )
            if updated != 1:
                raise StaleLease("failure delivery lease is no longer current")
            return False
        updated = InfrastructureFailureOutbox.objects.filter(
            pk=claim.outbox_id,
            status=InfrastructureFailureOutbox.Status.SENDING,
            lease_token=claim.lease_token,
            lease_until__gt=current_time,
        ).update(
            status=InfrastructureFailureOutbox.Status.SENT,
            sent_at=current_time,
            lease_token=None,
            lease_until=None,
            last_error_code=None,
        )
        if updated != 1:
            raise StaleLease("failure delivery lease is no longer current")
        return True

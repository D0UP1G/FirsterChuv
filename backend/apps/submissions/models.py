from uuid import uuid4

from django.conf import settings
from django.db import models


class Submission(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "В очереди"
        RUNNING = "RUNNING", "Проверяется"
        RETRY_WAIT = "RETRY_WAIT", "Повтор проверки"
        FINISHED = "FINISHED", "Проверена"
        INFRA_FAILED = "INFRA_FAILED", "Ошибка инфраструктуры"
        CANCELLED = "CANCELLED", "Отменена"

    class Verdict(models.TextChoices):
        OK = "OK", "OK"
        WA = "WA", "WA"
        TL = "TL", "TL"
        ML = "ML", "ML"
        RE = "RE", "RE"
        CE = "CE", "CE"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submissions")
    match_id = models.UUIDField(db_index=True)
    run_id = models.UUIDField(db_index=True)
    problem_id = models.UUIDField(db_index=True)
    language_id = models.CharField(max_length=64)
    source = models.TextField()
    source_sha256 = models.CharField(max_length=64)
    request_sha256 = models.CharField(max_length=64)
    idempotency_sha256 = models.CharField(max_length=64)
    received_at = models.DateTimeField()
    elapsed_ms = models.PositiveBigIntegerField()
    scoring_version = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(db_index=True)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verdict = models.CharField(max_length=8, choices=Verdict.choices, null=True, blank=True)
    compile_diagnostics = models.TextField(null=True, blank=True)
    metrics = models.JSONField(default=dict)
    internal_reason = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("actor", "idempotency_sha256"),
                name="submissions_actor_idempotency_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("status", "available_at", "received_at"), name="submissions_queue_idx"),
            models.Index(fields=("status", "lease_until"), name="submissions_lease_idx"),
        ]


class QueueCounter(models.Model):
    scope_key = models.CharField(max_length=48, primary_key=True)
    pending_count = models.PositiveIntegerField(default=0)


class ResultOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Ожидает публикации"
        SENDING = "SENDING", "Публикуется"
        SENT = "SENT", "Опубликована"

    submission = models.OneToOneField(Submission, on_delete=models.PROTECT, related_name="result_outbox")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(db_index=True)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class InfrastructureFailureOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Ожидает публикации"
        SENDING = "SENDING", "Публикуется"
        SENT = "SENT", "Опубликована"

    submission = models.OneToOneField(
        Submission,
        on_delete=models.PROTECT,
        related_name="infrastructure_failure_outbox",
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(db_index=True)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

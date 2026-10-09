from uuid import uuid4

from django.conf import settings
from django.db import models


class Draft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="drafts")
    run_id = models.UUIDField(db_index=True)
    problem_id = models.UUIDField(db_index=True)
    language_id = models.CharField(max_length=64)
    source = models.TextField()
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("actor", "run_id", "problem_id", "language_id"),
                name="drafts_actor_run_problem_language_unique",
            ),
        ]


class DraftRevision(models.Model):
    draft = models.ForeignKey(Draft, on_delete=models.CASCADE, related_name="history")
    revision = models.PositiveIntegerField()
    source = models.TextField()
    source_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("draft", "revision"), name="drafts_revision_unique"),
        ]

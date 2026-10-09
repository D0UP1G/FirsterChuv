from django.db import models


class ImmutableRecord(models.Model):
    """Application-level guard against changing a stored version in place."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("stored problem bundle records are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("stored problem bundle records are immutable")


class ProblemVersion(ImmutableRecord):
    class Readiness(models.TextChoices):
        NOT_READY = "NOT_READY", "Не готова"
        READY = "READY", "Готова"

    problem_id = models.UUIDField(db_index=True)
    version = models.CharField(max_length=64)
    checksum = models.CharField(max_length=64)
    readiness = models.CharField(max_length=16, choices=Readiness.choices)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("problem_id", "version"), name="problems_version_identity_unique"),
            models.UniqueConstraint(
                fields=("problem_id",),
                condition=models.Q(is_active=True),
                name="problems_one_active_version_per_problem",
            ),
        ]
        ordering = ("problem_id", "version")

class ProblemPublicData(ImmutableRecord):
    version = models.OneToOneField(ProblemVersion, on_delete=models.CASCADE, related_name="public_data")
    label = models.CharField(max_length=64)
    title = models.CharField(max_length=512)
    statement_markdown = models.TextField()
    examples = models.JSONField(default=list)
    time_limit_ms = models.PositiveBigIntegerField()
    memory_limit_bytes = models.PositiveBigIntegerField()
    languages = models.JSONField(default=list)


class ProblemPrivateData(ImmutableRecord):
    version = models.OneToOneField(ProblemVersion, on_delete=models.CASCADE, related_name="private_data")


class ProblemPublicAsset(ImmutableRecord):
    public_data = models.ForeignKey(ProblemPublicData, on_delete=models.CASCADE, related_name="assets")
    asset_id = models.CharField(max_length=64)
    media_type = models.CharField(max_length=32)
    contents = models.BinaryField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("public_data", "asset_id"), name="problems_public_asset_id_unique"),
        ]


class ProblemTestCase(ImmutableRecord):
    private_data = models.ForeignKey(ProblemPrivateData, on_delete=models.CASCADE, related_name="tests")
    ordinal = models.PositiveIntegerField()
    input_data = models.BinaryField()
    expected_output = models.BinaryField(null=True, blank=True)

    class Meta:
        ordering = ("ordinal",)
        constraints = [
            models.UniqueConstraint(fields=("private_data", "ordinal"), name="problems_test_ordinal_unique"),
        ]


class ProblemPrivateArtifact(ImmutableRecord):
    class Role(models.TextChoices):
        CHECKER = "checker", "Checker"
        VALIDATOR = "validator", "Validator"
        REFERENCE = "reference", "Reference solution"

    private_data = models.ForeignKey(ProblemPrivateData, on_delete=models.CASCADE, related_name="artifacts")
    role = models.CharField(max_length=16, choices=Role.choices)
    source_path = models.CharField(max_length=1024)
    language_id = models.CharField(max_length=64, null=True, blank=True)
    contents = models.BinaryField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("private_data", "role"), name="problems_private_artifact_role_unique"),
        ]

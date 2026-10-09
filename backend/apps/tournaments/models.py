"""Tournament metadata and lifecycle state owned by the platform domain."""

from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.text import slugify


def default_match_config():
    """Return a fresh MVP config matching the documented API example."""
    return {
        "match_duration_sec": 1200,
        "start_mode": "manual",
        "scoring_rule": {
            "order": ["solved_desc", "penalty_asc", "last_accepted_asc"],
            "wrong_attempt_penalty_sec": 60,
            "penalized_verdicts": ["WA", "TL", "ML", "RE"],
            "final_tie_policy": "rematch",
        },
    }


class Tournament(models.Model):
    class Formats(models.TextChoices):
        SINGLE_ELIMINATION = "single_elimination", "Олимпийская система"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Публичный"
        UNLISTED = "unlisted", "По ссылке"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        SCHEDULED = "scheduled", "Запланирован"
        RUNNING = "running", "Идёт"
        COMPLETED = "completed", "Завершён"
        ARCHIVED = "archived", "Архивирован"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    slug = models.SlugField(max_length=180, unique=True, editable=False)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=10000)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    format = models.CharField(
        max_length=32,
        choices=Formats.choices,
        default=Formats.SINGLE_ELIMINATION,
    )
    participant_limit = models.PositiveIntegerField(validators=[MinValueValidator(2)])
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    default_match_config = models.JSONField(default=default_match_config)
    active_participant_count = models.PositiveIntegerField(default=0, editable=False)
    roster_frozen_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tournaments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("starts_at", "created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(participant_limit__gte=2),
                name="tournaments_limit_at_least_two",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="tournaments_end_after_start",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            title_slug = slugify(self.title, allow_unicode=False)[:140].strip("-")
            self.slug = f"{title_slug or 'tournament'}-{self.id.hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class TournamentParticipant(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Активен"
        REMOVED = "REMOVED", "Снят"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tournament_entries",
    )
    seed = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(2147483647)],
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    added_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("status", "seed", "user__display_name", "user_id")
        constraints = [
            models.UniqueConstraint(
                fields=("tournament", "user"),
                name="unique_tournament_user_entry",
            ),
            models.UniqueConstraint(
                fields=("tournament", "seed"),
                condition=Q(status="ACTIVE", seed__isnull=False),
                name="unique_active_tournament_seed",
            ),
            models.CheckConstraint(
                condition=Q(seed__isnull=True) | Q(seed__gte=1),
                name="tournament_seed_positive_or_null",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.tournament}"

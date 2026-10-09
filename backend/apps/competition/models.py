"""Persisted tournament brackets and their execution runs."""

from uuid import uuid4

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Match(models.Model):
    class Kind(models.TextChoices):
        PLAYED = "MATCH", "Матч"
        BYE = "BYE", "Автоматический проход"

    class Status(models.TextChoices):
        WAITING = "WAITING", "Ожидает"
        READY = "READY", "Готов"
        RUNNING = "RUNNING", "Идёт"
        PAUSED = "PAUSED", "Пауза"
        FINALIZING = "FINALIZING", "Проверяются посылки"
        FINISHED = "FINISHED", "Завершён"
        TIED = "TIED", "Ничья"
        BYE = "BYE", "Автоматический проход"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    tournament = models.ForeignKey(
        "tournaments.Tournament",
        on_delete=models.CASCADE,
        related_name="matches",
    )
    bracket_key = models.CharField(max_length=32)
    round_index = models.PositiveSmallIntegerField()
    position = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=Kind.choices)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.WAITING,
    )
    next_match = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="previous_matches",
    )
    next_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    winner = models.ForeignKey(
        "tournaments.TournamentParticipant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="competition_matches_won",
    )
    current_run = models.OneToOneField(
        "competition.MatchRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_for_match",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("round_index", "position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("tournament", "round_index", "position"),
                name="unique_tournament_round_position",
            ),
            models.UniqueConstraint(
                fields=("tournament", "bracket_key"),
                name="unique_tournament_bracket_key",
            ),
            models.UniqueConstraint(
                fields=("next_match", "next_slot"),
                condition=Q(next_match__isnull=False),
                name="unique_match_advancement_target",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(next_match__isnull=True) & Q(next_slot__isnull=True))
                    | (
                        Q(next_match__isnull=False)
                        & Q(next_slot__in=(0, 1))
                        & ~Q(next_match=F("id"))
                    )
                ),
                name="match_advancement_target_complete",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(kind="BYE") & Q(status="BYE") & Q(winner__isnull=False))
                    | (
                        Q(kind="MATCH")
                        & Q(status__in=(
                            "WAITING",
                            "READY",
                            "RUNNING",
                            "PAUSED",
                            "FINALIZING",
                            "FINISHED",
                            "TIED",
                        ))
                    )
                ),
                name="match_bye_status_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tournament_id}:{self.bracket_key}"


class MatchSlot(models.Model):
    class Resolution(models.TextChoices):
        PLAYER = "PLAYER", "Участник"
        BYE = "BYE", "Пустой слот"
        WAITING = "WAITING", "Ожидает предыдущий матч"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="slots")
    slot_index = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    resolution = models.CharField(max_length=8, choices=Resolution.choices)
    participant = models.ForeignKey(
        "tournaments.TournamentParticipant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="competition_match_slots",
    )
    upstream_match = models.ForeignKey(
        Match,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="downstream_slots",
    )

    class Meta:
        ordering = ("match_id", "slot_index")
        constraints = [
            models.UniqueConstraint(
                fields=("match", "slot_index"),
                name="unique_match_slot_index",
            ),
            models.UniqueConstraint(
                fields=("match", "participant"),
                condition=Q(participant__isnull=False),
                name="unique_participant_per_match",
            ),
            models.CheckConstraint(
                condition=Q(slot_index__in=(0, 1)),
                name="match_slot_index_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(resolution="PLAYER")
                        & Q(participant__isnull=False)
                    )
                    | (
                        Q(resolution="BYE")
                        & Q(participant__isnull=True)
                        & Q(upstream_match__isnull=True)
                    )
                    | (
                        Q(resolution="WAITING")
                        & Q(participant__isnull=True)
                        & Q(upstream_match__isnull=False)
                    )
                ),
                name="match_slot_resolution_consistent",
            ),
            models.CheckConstraint(
                condition=Q(upstream_match__isnull=True)
                | ~Q(upstream_match=F("match")),
                name="match_slot_not_own_upstream",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.match_id}:{self.slot_index}"


class MatchRun(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Ожидает"
        READY = "READY", "Готов"
        RUNNING = "RUNNING", "Идёт"
        PAUSED = "PAUSED", "Пауза"
        FINALIZING = "FINALIZING", "Проверяются посылки"
        FINISHED = "FINISHED", "Завершён"
        TIED = "TIED", "Ничья"
        SUPERSEDED = "SUPERSEDED", "Заменён повторным матчем"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="runs")
    sequence = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.WAITING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    accumulated_pause_ms = models.PositiveBigIntegerField(default=0)
    allowed_duration_ms = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)]
    )
    score_rule = models.JSONField(default=dict)
    finished_at = models.DateTimeField(null=True, blank=True)
    winner = models.ForeignKey(
        "tournaments.TournamentParticipant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="competition_runs_won",
    )
    technical_reason = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("match_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("match", "sequence"),
                name="unique_match_run_sequence",
            ),
            models.CheckConstraint(
                condition=Q(allowed_duration_ms__gte=1),
                name="match_run_duration_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.match_id} run {self.sequence}"


class BracketCommandReceipt(models.Model):
    """Durable idempotency receipt for an administrator bracket command."""

    class Action(models.TextChoices):
        SET_PAIRINGS = "bracket.pairings", "Ручные пары"
        RESET = "bracket.reset", "Сброс сетки"

    id = models.BigAutoField(primary_key=True)
    tournament = models.ForeignKey(
        "tournaments.Tournament",
        on_delete=models.CASCADE,
        related_name="bracket_command_receipts",
    )
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="bracket_command_receipts",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    idempotency_sha256 = models.CharField(max_length=64)
    request_sha256 = models.CharField(max_length=64)
    reason = models.CharField(max_length=500)
    response_payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tournament", "idempotency_sha256"),
                name="unique_tournament_bracket_command_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tournament_id}:{self.action}:{self.id}"

"""Durable event log; UUID scopes are decoupled from pending competition ORM."""

from django.db import models
from django.db.models import Q


class MatchEvent(models.Model):
    class Types(models.TextChoices):
        SCORE_CHANGED = "score.changed", "Изменение счёта"
        ADMIN_ACTION = "match.admin_action", "Действие администратора"

    # BigAutoField is the global durable cursor used by snapshot and SSE readers.
    id = models.BigAutoField(primary_key=True)
    tournament_id = models.UUIDField()
    match_id = models.UUIDField()
    run_id = models.UUIDField()
    event_type = models.CharField(max_length=32, choices=Types.choices)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(event_type__in=("score.changed", "match.admin_action")),
                name="events_supported_public_type",
            )
        ]
        indexes = [
            models.Index(fields=("tournament_id", "id"), name="events_tournament_cursor"),
            models.Index(fields=("match_id", "id"), name="events_match_cursor"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} #{self.id} for {self.match_id}"


class MatchSnapshot(models.Model):
    """Latest public-safe state for one match/run and its durable event cursor."""

    match_id = models.UUIDField(primary_key=True)
    run_id = models.UUIDField()
    last_event_id = models.PositiveBigIntegerField(default=0)
    payload = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(last_event_id__gte=0), name="events_snapshot_nonnegative_cursor")]

    def __str__(self) -> str:
        return f"snapshot {self.match_id} @ {self.last_event_id}"

"""Transactional roster operations; HTTP policy remains in the API layer."""

from dataclasses import dataclass
from typing import ClassVar
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.tournaments.models import Tournament, TournamentParticipant


@dataclass(eq=False)
class RosterMutationError(Exception):
    message: str
    status_code: ClassVar[int] = 409
    code: ClassVar[str] = "roster_conflict"

    def __str__(self) -> str:
        return self.message


class EntrantUnavailable(RosterMutationError):
    status_code = 400
    code = "invalid_entrant"


class EntrantNotFound(RosterMutationError):
    status_code = 404
    code = "not_found"


class RosterCapacityReached(RosterMutationError):
    code = "capacity_reached"


class RosterFrozen(RosterMutationError):
    code = "roster_frozen"


class SeedConflict(RosterMutationError):
    code = "seed_conflict"


class AlreadyAssigned(Exception):
    """Internal savepoint signal used to undo a duplicate capacity increment."""


EDITABLE_TOURNAMENT_STATUSES = (
    Tournament.Status.DRAFT,
    Tournament.Status.SCHEDULED,
)


def _capacity_increment(tournament_id: UUID) -> bool:
    """Acquire a SQLite write before reading roster rows and reserve one slot."""
    now = timezone.now()
    return bool(
        Tournament.objects.filter(
            pk=tournament_id,
            roster_frozen_at__isnull=True,
            status__in=EDITABLE_TOURNAMENT_STATUSES,
            active_participant_count__lt=F("participant_limit"),
        ).update(
            active_participant_count=F("active_participant_count") + 1,
            updated_at=now,
        )
    )


def _raise_capacity_or_frozen(tournament_id: UUID) -> None:
    tournament = Tournament.objects.filter(pk=tournament_id).only(
        "status", "roster_frozen_at", "active_participant_count", "participant_limit"
    ).first()
    if tournament is None:
        raise EntrantNotFound("Турнир не найден.")
    if (
        tournament.roster_frozen_at is not None
        or tournament.status not in EDITABLE_TOURNAMENT_STATUSES
    ):
        raise RosterFrozen("Состав нельзя изменить в текущем состоянии турнира.")
    raise RosterCapacityReached("Достигнут лимит участников турнира.")


def assign_participant(
    tournament_id: UUID,
    user_id: UUID,
    *,
    seed: int | None = None,
) -> tuple[TournamentParticipant, bool]:
    """Add or reactivate an account, preserving its unique tournament row."""
    user = User.objects.filter(pk=user_id, is_active=True).only("id", "role").first()
    if user is None or user.role != User.Roles.PARTICIPANT:
        raise EntrantUnavailable("Назначить можно только активного participant.")

    current = TournamentParticipant.objects.select_related("user").filter(
        tournament_id=tournament_id,
        user_id=user_id,
        status=TournamentParticipant.Status.ACTIVE,
    ).first()
    if current is not None:
        if seed is not None and seed != current.seed:
            raise SeedConflict("Участник уже назначен; измените seed отдельным PATCH.")
        return current, False

    try:
        with transaction.atomic():
            try:
                with transaction.atomic():
                    if not _capacity_increment(tournament_id):
                        _raise_capacity_or_frozen(tournament_id)

                    entry = (
                        TournamentParticipant.objects.select_related("user")
                        .filter(tournament_id=tournament_id, user_id=user_id)
                        .first()
                    )
                    if entry is not None and entry.status == TournamentParticipant.Status.ACTIVE:
                        raise AlreadyAssigned

                    if entry is None:
                        entry = TournamentParticipant.objects.create(
                            tournament_id=tournament_id,
                            user_id=user_id,
                            seed=seed,
                        )
                    else:
                        entry.seed = seed
                        entry.status = TournamentParticipant.Status.ACTIVE
                        entry.removed_at = None
                        entry.save(update_fields=("seed", "status", "removed_at"))
                    entry = TournamentParticipant.objects.select_related("user").get(pk=entry.pk)
            except AlreadyAssigned:
                # Roll back the attempted counter increment from the savepoint.
                entry = TournamentParticipant.objects.select_related("user").get(
                    tournament_id=tournament_id,
                    user_id=user_id,
                    status=TournamentParticipant.Status.ACTIVE,
                )
                if seed is not None and seed != entry.seed:
                    raise SeedConflict("Участник уже назначен; измените seed отдельным PATCH.")
                return entry, False
        return entry, True
    except IntegrityError as exc:
        existing = TournamentParticipant.objects.filter(
            tournament_id=tournament_id,
            user_id=user_id,
            status=TournamentParticipant.Status.ACTIVE,
        ).first()
        if existing is not None:
            if seed is None or seed == existing.seed:
                return existing, False
            raise SeedConflict("Участник уже назначен с другим seed.") from exc
        if seed is not None and TournamentParticipant.objects.filter(
            tournament_id=tournament_id,
            seed=seed,
            status=TournamentParticipant.Status.ACTIVE,
        ).exists():
            raise SeedConflict("Этот seed уже используется в турнире.") from exc
        raise RosterMutationError("Не удалось сохранить состав; повторите запрос.") from exc


def set_participant_seed(tournament_id: UUID, user_id: UUID, seed: int | None):
    with transaction.atomic():
        tournament = Tournament.objects.filter(pk=tournament_id).first()
        if tournament is None:
            raise EntrantNotFound("Турнир не найден.")
        if (
            tournament.roster_frozen_at is not None
            or tournament.status not in EDITABLE_TOURNAMENT_STATUSES
        ):
            raise RosterFrozen("Seed нельзя изменить после заморозки состава.")
        entry = TournamentParticipant.objects.select_related("user").filter(
            tournament=tournament,
            user_id=user_id,
            status=TournamentParticipant.Status.ACTIVE,
        ).first()
        if entry is None:
            raise EntrantNotFound("Активный участник не найден.")
        entry.seed = seed
        try:
            entry.save(update_fields=("seed",))
        except IntegrityError as exc:
            raise SeedConflict("Этот seed уже используется в турнире.") from exc
        return TournamentParticipant.objects.select_related("user").get(pk=entry.pk)


def remove_participant(tournament_id: UUID, user_id: UUID) -> bool:
    """Logically remove an entrant; never delete its row or user reference."""
    with transaction.atomic():
        now = timezone.now()
        changed = Tournament.objects.filter(
            pk=tournament_id,
            roster_frozen_at__isnull=True,
            status__in=EDITABLE_TOURNAMENT_STATUSES,
            active_participant_count__gt=0,
            participants__user_id=user_id,
            participants__status=TournamentParticipant.Status.ACTIVE,
        ).update(
            active_participant_count=F("active_participant_count") - 1,
            updated_at=now,
        )
        if changed == 0:
            tournament = Tournament.objects.filter(pk=tournament_id).only(
                "status", "roster_frozen_at"
            ).first()
            if tournament is None:
                raise EntrantNotFound("Турнир не найден.")
            entry = TournamentParticipant.objects.filter(
                tournament_id=tournament_id,
                user_id=user_id,
                status=TournamentParticipant.Status.ACTIVE,
            ).first()
            if entry is None:
                return False
            raise RosterFrozen("Состав нельзя изменить в текущем состоянии турнира.")

        removed = TournamentParticipant.objects.filter(
            tournament_id=tournament_id,
            user_id=user_id,
            status=TournamentParticipant.Status.ACTIVE,
        ).update(status=TournamentParticipant.Status.REMOVED, removed_at=now)
        if removed == 0:
            # Keep the counter and row change atomic when a request races a removal.
            raise EntrantNotFound("Активный участник не найден.")
        return True

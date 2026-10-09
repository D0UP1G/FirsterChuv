"""Transactional roster operations; HTTP policy remains in the API layer."""

from dataclasses import dataclass
from functools import wraps
import hashlib
import secrets
import time
from typing import ClassVar
from uuid import UUID

from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Q
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.tournaments.models import (
    Invite,
    InviteAcceptance,
    Tournament,
    TournamentParticipant,
)


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


class RosterNotReady(RosterMutationError):
    code = "roster_not_ready"


class RosterInvariantViolation(RosterMutationError):
    status_code = 500
    code = "roster_invariant_violation"


class RosterDatabaseBusy(RosterMutationError):
    status_code = 503
    code = "database_busy"


class TournamentUpdateConflict(RosterMutationError):
    code = "tournament_changed"


class InviteMutationError(Exception):
    status_code = 409
    code = "invite_conflict"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InviteNotFound(InviteMutationError):
    status_code = 404
    code = "not_found"


class InviteUnavailable(InviteMutationError):
    status_code = 410
    code = "invite_unavailable"


class AlreadyAssigned(Exception):
    """Internal savepoint signal used to undo a duplicate capacity increment."""


EDITABLE_TOURNAMENT_STATUSES = (
    Tournament.Status.DRAFT,
    Tournament.Status.SCHEDULED,
)


def retry_sqlite_locked_write(function):
    """Retry brief SQLite write-lock collisions; never hide other DB errors."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        for attempt in range(3):
            try:
                return function(*args, **kwargs)
            except OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                if attempt == 2:
                    raise RosterDatabaseBusy(
                        "База занята; повторите изменение состава позже."
                    ) from exc
                time.sleep(0.01 * (attempt + 1))

    return wrapped


def hash_invite_token(token: str) -> str:
    """Return the only token representation persisted by the application."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_invite_token() -> str:
    """Generate an unguessable URL-safe secret; callers reveal it only once."""
    return secrets.token_urlsafe(32)


def invite_for_token(token: str) -> Invite:
    invite = (
        Invite.objects.select_related("tournament")
        .filter(token_hash=hash_invite_token(token))
        .first()
    )
    if invite is None:
        raise InviteNotFound("Приглашение не найдено.")
    ensure_invite_usable(invite)
    return invite


def ensure_invite_usable(invite: Invite, *, now=None) -> None:
    now = now or timezone.now()
    if invite.revoked_at is not None:
        raise InviteUnavailable("Приглашение отозвано.")
    if invite.expires_at is not None and invite.expires_at <= now:
        raise InviteUnavailable("Срок действия приглашения истёк.")
    if invite.max_uses is not None and invite.used_count >= invite.max_uses:
        raise InviteUnavailable("Лимит активаций приглашения исчерпан.")


def create_invite(
    tournament: Tournament,
    created_by: User,
    *,
    expires_at,
    max_uses,
) -> tuple[Invite, str]:
    if (
        tournament.roster_frozen_at is not None
        or tournament.status not in EDITABLE_TOURNAMENT_STATUSES
    ):
        raise RosterFrozen("Нельзя создавать приглашения после заморозки состава.")

    for attempt in range(3):
        token = new_invite_token()
        try:
            with transaction.atomic():
                # Repeat the lifecycle guard in the insert statement so a concurrent
                # freeze/status transition cannot slip between read and create.
                if not Tournament.objects.filter(
                    pk=tournament.pk,
                    roster_frozen_at__isnull=True,
                    status__in=EDITABLE_TOURNAMENT_STATUSES,
                ).exists():
                    raise RosterFrozen(
                        "Нельзя создавать приглашения после заморозки состава."
                    )
                invite = Invite.objects.create(
                    tournament_id=tournament.pk,
                    token_hash=hash_invite_token(token),
                    expires_at=expires_at,
                    max_uses=max_uses,
                    created_by=created_by,
                )
            return invite, token
        except IntegrityError:
            if attempt == 2:
                raise
    raise RuntimeError("Не удалось создать уникальный токен приглашения.")


@retry_sqlite_locked_write
def accept_invite(token: str, user: User) -> tuple[Invite, bool]:
    """Atomically consume one use and add a participant; retries are idempotent."""
    if not user.is_active or user.role != User.Roles.PARTICIPANT:
        raise EntrantUnavailable("Принять приглашение может только активный participant.")

    token_digest = hash_invite_token(token)
    try:
        with transaction.atomic():
            invite = (
                Invite.objects.select_related("tournament")
                .filter(token_hash=token_digest)
                .first()
            )
            if invite is None:
                raise InviteNotFound("Приглашение не найдено.")

            if InviteAcceptance.objects.filter(invite=invite, user=user).exists():
                return invite, False

            now = timezone.now()
            ensure_invite_usable(invite, now=now)
            changed = (
                Invite.objects.filter(
                    pk=invite.pk,
                    revoked_at__isnull=True,
                    tournament__roster_frozen_at__isnull=True,
                    tournament__status__in=EDITABLE_TOURNAMENT_STATUSES,
                )
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
                .filter(Q(max_uses__isnull=True) | Q(used_count__lt=F("max_uses")))
                .update(used_count=F("used_count") + 1)
            )
            if changed == 0:
                invite.refresh_from_db()
                ensure_invite_usable(invite, now=now)
                tournament = Tournament.objects.filter(pk=invite.tournament_id).first()
                if tournament is not None and (
                    tournament.roster_frozen_at is not None
                    or tournament.status not in EDITABLE_TOURNAMENT_STATUSES
                ):
                    raise RosterFrozen(
                        "Принять приглашение нельзя после заморозки состава."
                    )
                raise InviteUnavailable("Приглашение больше нельзя активировать.")

            assign_participant(invite.tournament_id, user.id)
            InviteAcceptance.objects.create(invite=invite, user=user)
        return invite, True
    except IntegrityError:
        # A unique acceptance can win a concurrent retry. Roll back the whole
        # transaction first, then report the existing acceptance without a use.
        accepted = InviteAcceptance.objects.filter(
            invite__token_hash=token_digest,
            user=user,
        ).exists()
        if accepted:
            invite = Invite.objects.select_related("tournament").get(
                token_hash=token_digest
            )
            return invite, False
        raise


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


@retry_sqlite_locked_write
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


@retry_sqlite_locked_write
def set_participant_seed(tournament_id: UUID, user_id: UUID, seed: int | None):
    with transaction.atomic():
        try:
            changed = TournamentParticipant.objects.filter(
                tournament_id=tournament_id,
                user_id=user_id,
                status=TournamentParticipant.Status.ACTIVE,
                tournament__roster_frozen_at__isnull=True,
                tournament__status__in=EDITABLE_TOURNAMENT_STATUSES,
            ).update(seed=seed)
        except IntegrityError as exc:
            raise SeedConflict("Этот seed уже используется в турнире.") from exc
        if changed == 0:
            tournament = Tournament.objects.filter(pk=tournament_id).first()
            if tournament is None:
                raise EntrantNotFound("Турнир не найден.")
            if (
                tournament.roster_frozen_at is not None
                or tournament.status not in EDITABLE_TOURNAMENT_STATUSES
            ):
                raise RosterFrozen("Seed нельзя изменить после заморозки состава.")
            if not TournamentParticipant.objects.filter(
                tournament_id=tournament_id,
                user_id=user_id,
                status=TournamentParticipant.Status.ACTIVE,
            ).exists():
                raise EntrantNotFound("Активный участник не найден.")
            raise RosterMutationError("Не удалось обновить seed; повторите запрос.")
        try:
            entry = TournamentParticipant.objects.select_related("user").get(
                tournament_id=tournament_id,
                user_id=user_id,
            )
        except TournamentParticipant.DoesNotExist as exc:
            raise EntrantNotFound("Активный участник не найден.") from exc
        return entry


@retry_sqlite_locked_write
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


@retry_sqlite_locked_write
def freeze_roster(tournament_id: UUID) -> list[TournamentParticipant]:
    """Freeze and return the canonical active roster inside the caller's transaction.

    Bracket generation must call this function from its own `transaction.atomic()`
    block. This function's atomic block is a savepoint when called from that outer
    transaction, so a later bracket error rolls the freeze back with the bracket.
    """
    now = timezone.now()
    with transaction.atomic():
        changed = Tournament.objects.filter(
            pk=tournament_id,
            roster_frozen_at__isnull=True,
            status__in=EDITABLE_TOURNAMENT_STATUSES,
            active_participant_count__gte=2,
        ).update(roster_frozen_at=now, updated_at=now)
        tournament = Tournament.objects.filter(pk=tournament_id).first()
        if tournament is None:
            raise EntrantNotFound("Турнир не найден.")
        if changed == 0 and tournament.roster_frozen_at is None:
            if tournament.status not in EDITABLE_TOURNAMENT_STATUSES:
                raise RosterFrozen("Турнир нельзя заморозить в текущем состоянии.")
            actual_count = TournamentParticipant.objects.filter(
                tournament_id=tournament_id,
                status=TournamentParticipant.Status.ACTIVE,
            ).count()
            if actual_count != tournament.active_participant_count:
                raise RosterInvariantViolation(
                    "Число активных участников не совпадает со счётчиком турнира."
                )
            raise RosterNotReady("Для генерации сетки нужны как минимум два участника.")

        roster = list(
            TournamentParticipant.objects.select_related("user")
            .filter(
                tournament_id=tournament_id,
                status=TournamentParticipant.Status.ACTIVE,
            )
            .order_by(F("seed").asc(nulls_last=True), "user_id")
        )
        if len(roster) != tournament.active_participant_count:
            raise RosterInvariantViolation(
                "Число активных участников не совпадает со счётчиком турнира."
            )
        if len(roster) < 2:
            raise RosterNotReady("Для генерации сетки нужны как минимум два участника.")
        if any(
            not entry.user.is_active or entry.user.role != User.Roles.PARTICIPANT
            for entry in roster
        ):
            raise RosterNotReady(
                "В составе есть неактивная учётная запись или пользователь с ролью admin."
            )
        return roster

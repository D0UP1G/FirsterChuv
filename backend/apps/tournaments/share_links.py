"""Read-only share links for unlisted tournaments."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.tournaments.models import Tournament, TournamentShareLink


class ShareLinkError(ValueError):
    """Invalid share-link request or unavailable access grant."""

    status_code = 409
    code = "share_link_unavailable"


class ShareLinkNotFound(ShareLinkError):
    status_code = 404
    code = "not_found"


def hash_share_token(token: str) -> str:
    """Return the only token representation stored in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_share_token() -> str:
    """Generate 256 bits of URL-safe entropy; callers reveal it once."""
    return secrets.token_urlsafe(32)


def create_share_link(
    tournament: Tournament,
    actor: User,
    *,
    expires_at: datetime,
    now: datetime | None = None,
) -> tuple[TournamentShareLink, str]:
    now = now or timezone.now()
    if tournament.visibility != Tournament.Visibility.UNLISTED:
        raise ShareLinkError("Ссылка доступна только для турнира «по ссылке».")
    if timezone.is_naive(expires_at) or expires_at <= now:
        raise ShareLinkError("Срок действия ссылки должен быть в будущем.")

    for attempt in range(3):
        token = new_share_token()
        try:
            with transaction.atomic():
                # Reserve SQLite's writer before the visibility re-check so a
                # concurrent change cannot pass a deferred read transaction.
                changed = Tournament.objects.filter(pk=tournament.pk).update(
                    updated_at=models.F("updated_at")
                )
                if not changed:
                    raise ShareLinkError("Турнир не найден.")
                current_visibility = Tournament.objects.filter(
                    pk=tournament.pk
                ).values_list("visibility", flat=True).first()
                if current_visibility != Tournament.Visibility.UNLISTED:
                    raise ShareLinkError(
                        "Ссылка доступна только для турнира «по ссылке»."
                    )
                link = TournamentShareLink.objects.create(
                    tournament_id=tournament.pk,
                    token_hash=hash_share_token(token),
                    expires_at=expires_at,
                    created_by=actor,
                )
            return link, token
        except IntegrityError:
            if attempt == 2:
                raise
    raise RuntimeError("Не удалось создать уникальный токен ссылки.")


def revoke_share_link(
    tournament_id: UUID | str,
    share_link_id: UUID | str,
    *,
    now: datetime | None = None,
) -> None:
    now = now or timezone.now()
    link = TournamentShareLink.objects.filter(
        pk=share_link_id,
        tournament_id=tournament_id,
    ).first()
    if link is None:
        raise ShareLinkNotFound("Ссылка не найдена.")
    if link.revoked_at is None:
        TournamentShareLink.objects.filter(
            pk=link.pk,
            revoked_at__isnull=True,
        ).update(revoked_at=now)


def token_grants_access(
    tournament_id: UUID,
    token: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    if not isinstance(token, str) or not token or len(token) > 128:
        return False
    # Generated tokens are URL-safe ASCII. Reject malformed values before
    # hashing/querying so arbitrary Unicode/header payloads are not accepted.
    try:
        encoded = token.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        return False
    if any(byte < 0x21 or byte > 0x7E for byte in encoded):
        return False
    now = now or timezone.now()
    return TournamentShareLink.objects.filter(
        tournament_id=tournament_id,
        token_hash=hash_share_token(token),
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).exists()

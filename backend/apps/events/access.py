"""Public match access adapter; unlisted share tokens are a separate slice."""

from uuid import UUID

from backend.apps.common.contracts import PublicAccessContext
from backend.apps.tournaments.models import Tournament


class PublicAccessDenied(PermissionError):
    """The tournament is not currently available to anonymous viewers."""


class DjangoPublicAccess:
    """Fail-closed public-only implementation of the v1 access port."""

    def assert_can_view(
        self, tournament_id: UUID, share_token: str | None = None
    ) -> PublicAccessContext:
        try:
            normalized_id = UUID(str(tournament_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise PublicAccessDenied("Публичный объект не найден.") from error

        visibility = Tournament.objects.filter(pk=normalized_id).values_list(
            "visibility", flat=True
        ).first()
        if visibility != Tournament.Visibility.PUBLIC:
            # Unlisted access remains denied until P1-03 implements hashed,
            # expiring and revocable share tokens.
            raise PublicAccessDenied("Публичный объект не найден.")

        return PublicAccessContext(tournament_id=normalized_id, public=True)

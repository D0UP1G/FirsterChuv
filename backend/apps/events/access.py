"""Public and unlisted tournament access adapter."""

from uuid import UUID

from backend.apps.common.contracts import PublicAccessContext
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.share_links import token_grants_access


class PublicAccessDenied(PermissionError):
    """The tournament is not currently available to anonymous viewers."""


class DjangoPublicAccess:
    """Fail-closed implementation of the public read-only v1 access port."""

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
        if visibility == Tournament.Visibility.PUBLIC:
            return PublicAccessContext(tournament_id=normalized_id, public=True)
        if visibility != Tournament.Visibility.UNLISTED or not token_grants_access(
            normalized_id, share_token
        ):
            raise PublicAccessDenied("Публичный объект не найден.")

        return PublicAccessContext(tournament_id=normalized_id, public=False)

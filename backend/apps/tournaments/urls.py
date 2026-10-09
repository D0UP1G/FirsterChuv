"""Tournament routes use the project-wide no-trailing-slash contract."""

from rest_framework.routers import SimpleRouter
from django.urls import path

from backend.apps.tournaments.views import (
    AdminUserDirectoryView,
    InviteAcceptView,
    InvitePreviewView,
    TournamentInviteRevokeView,
    TournamentInvitesView,
    TournamentViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("tournaments", TournamentViewSet, basename="tournament")

urlpatterns = router.urls
urlpatterns += [
    path("admin/users", AdminUserDirectoryView.as_view(), name="admin-user-directory"),
    path(
        "tournaments/<uuid:tournament_id>/invites",
        TournamentInvitesView.as_view(),
        name="tournament-invites",
    ),
    path(
        "tournaments/<uuid:tournament_id>/invites/<uuid:invite_id>",
        TournamentInviteRevokeView.as_view(),
        name="tournament-invite-revoke",
    ),
    path("invites/<str:token>", InvitePreviewView.as_view(), name="invite-preview"),
    path(
        "invites/<str:token>/accept",
        InviteAcceptView.as_view(),
        name="invite-accept",
    ),
]

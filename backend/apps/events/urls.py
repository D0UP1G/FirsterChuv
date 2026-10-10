from django.urls import path

from backend.apps.events.public_views import (
    PublicBracketView,
    PublicMatchEventsView,
    PublicTournamentListView,
)
from backend.apps.events.views import PublicMatchSnapshotView


urlpatterns = [
    path(
        "public/matches/<uuid:match_id>",
        PublicMatchSnapshotView.as_view(),
        name="public-match-snapshot",
    ),
    path(
        "public/matches/<uuid:match_id>/events",
        PublicMatchEventsView.as_view(),
        name="public-match-events",
    ),
    path("public/tournaments", PublicTournamentListView.as_view(), name="public-tournaments"),
    path(
        "public/tournaments/<uuid:tournament_id>/bracket",
        PublicBracketView.as_view(),
        name="public-tournament-bracket",
    ),
]

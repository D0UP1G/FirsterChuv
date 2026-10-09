from django.urls import path

from backend.apps.competition.views import (
    GenerateBracketView,
    MatchDetailView,
    ResetBracketView,
    StartMatchView,
    SetFirstRoundPairingsView,
    TournamentBracketView,
)


urlpatterns = [
    path(
        "matches/<uuid:match_id>",
        MatchDetailView.as_view(),
        name="match-detail",
    ),
    path(
        "matches/<uuid:match_id>/start",
        StartMatchView.as_view(),
        name="match-start",
    ),
    path(
        "tournaments/<uuid:tournament_id>/bracket/generate",
        GenerateBracketView.as_view(),
        name="tournament-bracket-generate",
    ),
    path(
        "tournaments/<uuid:tournament_id>/bracket/pairings",
        SetFirstRoundPairingsView.as_view(),
        name="tournament-bracket-pairings",
    ),
    path(
        "tournaments/<uuid:tournament_id>/bracket/reset",
        ResetBracketView.as_view(),
        name="tournament-bracket-reset",
    ),
    path(
        "tournaments/<uuid:tournament_id>/bracket",
        TournamentBracketView.as_view(),
        name="tournament-bracket",
    ),
]

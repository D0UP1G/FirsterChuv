from django.urls import path

from backend.apps.competition.views import (
    ExtendMatchView,
    GenerateBracketView,
    MatchDetailView,
    PauseMatchView,
    RematchView,
    ReplaceParticipantView,
    ResetBracketView,
    ResumeMatchView,
    StartMatchView,
    SetFirstRoundPairingsView,
    TechnicalResultView,
    TournamentBracketView,
)


urlpatterns = [
    path("matches/<uuid:match_id>/pause", PauseMatchView.as_view(), name="match-pause"),
    path("matches/<uuid:match_id>/resume", ResumeMatchView.as_view(), name="match-resume"),
    path("matches/<uuid:match_id>/extend", ExtendMatchView.as_view(), name="match-extend"),
    path(
        "matches/<uuid:match_id>/technical-result",
        TechnicalResultView.as_view(),
        name="match-technical-result",
    ),
    path("matches/<uuid:match_id>/rematches", RematchView.as_view(), name="match-rematch"),
    path(
        "matches/<uuid:match_id>/replacements",
        ReplaceParticipantView.as_view(),
        name="match-replacement",
    ),
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

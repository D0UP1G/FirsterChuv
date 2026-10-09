from django.urls import path

from backend.apps.competition.views import GenerateBracketView, TournamentBracketView


urlpatterns = [
    path(
        "tournaments/<uuid:tournament_id>/bracket/generate",
        GenerateBracketView.as_view(),
        name="tournament-bracket-generate",
    ),
    path(
        "tournaments/<uuid:tournament_id>/bracket",
        TournamentBracketView.as_view(),
        name="tournament-bracket",
    ),
]

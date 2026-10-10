from django.urls import path

from .views import AdminProblemVersionListView
from .workspace_views import MatchProblemLanguagesView, MatchProblemStatementView

urlpatterns = [
    path("problems", AdminProblemVersionListView.as_view(), name="problem-catalog"),
    path(
        "matches/<uuid:match_id>/problems/<uuid:problem_id>",
        MatchProblemStatementView.as_view(),
        name="match-problem-statement",
    ),
    path(
        "matches/<uuid:match_id>/problems/<uuid:problem_id>/languages",
        MatchProblemLanguagesView.as_view(),
        name="match-problem-languages",
    ),
]

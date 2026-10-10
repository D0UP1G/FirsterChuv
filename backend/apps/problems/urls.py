from django.urls import path

from .views import AdminProblemVersionListView
from .workspace_views import MatchProblemLanguagesView, MatchProblemStatementView, ProblemAssetView

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
    path("problem-assets/<uuid:asset_id>", ProblemAssetView.as_view(), name="problem-asset"),
]

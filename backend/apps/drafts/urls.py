from django.urls import path

from backend.apps.drafts.views import MatchDraftView

urlpatterns = [
    path(
        "matches/<uuid:match_id>/problems/<uuid:problem_id>/draft",
        MatchDraftView.as_view(),
        name="match-draft",
    ),
]

"""Versioned submission routes; included below /api/v1."""

from django.urls import path

from .views import MatchSubmissionsView, SubmissionDetailView, SubmissionSourceView

urlpatterns = [
    path("matches/<uuid:match_id>/submissions", MatchSubmissionsView.as_view(), name="match-submissions"),
    path("submissions/<uuid:submission_id>", SubmissionDetailView.as_view(), name="submission-detail"),
    path("submissions/<uuid:submission_id>/source", SubmissionSourceView.as_view(), name="submission-source"),
]

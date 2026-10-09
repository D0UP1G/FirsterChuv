"""Versioned API registry; domain routes remain in their owning apps."""

from django.urls import include, path

from backend.apps.accounts.views import CurrentUserView

urlpatterns = [
    path("auth/", include("backend.apps.accounts.urls")),
    path("", include("backend.apps.tournaments.urls")),
    path("", include("backend.apps.submissions.urls")),
    path("me", CurrentUserView.as_view(), name="current-user"),
]

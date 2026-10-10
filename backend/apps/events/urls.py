from django.urls import path

from backend.apps.events.views import PublicMatchSnapshotView


urlpatterns = [
    path(
        "public/matches/<uuid:match_id>",
        PublicMatchSnapshotView.as_view(),
        name="public-match-snapshot",
    ),
]

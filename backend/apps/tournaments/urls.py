"""Tournament routes use the project-wide no-trailing-slash contract."""

from rest_framework.routers import SimpleRouter
from django.urls import path

from backend.apps.tournaments.views import AdminUserDirectoryView, TournamentViewSet

router = SimpleRouter(trailing_slash=False)
router.register("tournaments", TournamentViewSet, basename="tournament")

urlpatterns = router.urls
urlpatterns += [
    path("admin/users", AdminUserDirectoryView.as_view(), name="admin-user-directory"),
]

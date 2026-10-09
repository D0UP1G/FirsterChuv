"""Tournament routes use the project-wide no-trailing-slash contract."""

from rest_framework.routers import SimpleRouter

from backend.apps.tournaments.views import TournamentViewSet

router = SimpleRouter(trailing_slash=False)
router.register("tournaments", TournamentViewSet, basename="tournament")

urlpatterns = router.urls

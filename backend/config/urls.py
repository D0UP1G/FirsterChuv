"""Root routes. Domain routes are mounted below the versioned API prefix."""

from django.urls import include, path

from backend.apps.common.views import health

urlpatterns = [
    path("health", health, name="health"),
    path("api/v1/", include("backend.apps.common.api_urls")),
]

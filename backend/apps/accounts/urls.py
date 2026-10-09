"""Versioned account/auth endpoints; paths are mounted below /api/v1."""

from django.urls import path

from backend.apps.accounts.views import CsrfTokenView, LoginView, LogoutView, RegisterView

urlpatterns = [
    path("csrf", CsrfTokenView.as_view(), name="auth-csrf"),
    path("register", RegisterView.as_view(), name="auth-register"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
]

import os
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import TestCase

from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from backend.apps.accounts.models import User
from backend.apps.accounts.permissions import IsApplicationAdmin, IsParticipant


class _AdminMutationProbe(APIView):
    permission_classes = [IsApplicationAdmin]

    def post(self, request):
        return Response({"changed": True})


class _ParticipantAccessProbe(APIView):
    permission_classes = [IsParticipant]

    def post(self, request):
        return Response({"allowed": True})


class CreateAdminCommandTests(TestCase):
    command_options = {
        "email": "admin@example.test",
        "display_name": "Tournament Admin",
    }

    def run_command(self, stdout=None):
        return call_command("create_admin", stdout=stdout or StringIO(), **self.command_options)

    def test_creates_application_admin_without_django_superuser_flags_or_secret_output(self):
        secret = "N0n-Guessable Admin Passphrase 2026!"
        output = StringIO()
        with patch.dict(os.environ, {"DJANGO_ADMIN_PASSWORD": secret}):
            self.run_command(stdout=output)

        admin = User.objects.get(email="admin@example.test")
        self.assertEqual(admin.role, User.Roles.ADMIN)
        self.assertTrue(admin.is_active)
        self.assertFalse(admin.is_staff)
        self.assertFalse(admin.is_superuser)
        self.assertTrue(admin.check_password(secret))
        self.assertNotIn(secret, output.getvalue())

    def test_existing_admin_is_idempotent_and_password_is_not_rotated(self):
        original = "Original-Safe-Admin-Passphrase-2026!"
        replacement = "Different-Safe-Admin-Passphrase-2026!"
        admin = User.objects.create_user(
            email="admin@example.test",
            display_name="Original Admin",
            password=original,
            role=User.Roles.ADMIN,
        )
        output = StringIO()

        with patch.dict(os.environ, {"DJANGO_ADMIN_PASSWORD": replacement}):
            self.run_command(stdout=output)

        admin.refresh_from_db()
        self.assertTrue(admin.check_password(original))
        self.assertFalse(admin.check_password(replacement))
        self.assertEqual(admin.display_name, "Original Admin")
        self.assertIn("unchanged", output.getvalue())
        self.assertNotIn(replacement, output.getvalue())

    def test_existing_participant_is_never_promoted(self):
        participant = User.objects.create_user(
            email="admin@example.test",
            display_name="Existing Participant",
            password="unused",
        )

        with patch.dict(os.environ, {"DJANGO_ADMIN_PASSWORD": "N0n-Guessable Admin Passphrase 2026!"}):
            with self.assertRaisesMessage(CommandError, "refusing to promote"):
                self.run_command()

        participant.refresh_from_db()
        self.assertEqual(participant.role, User.Roles.PARTICIPANT)
        self.assertEqual(User.objects.count(), 1)

    def test_missing_secret_in_noninteractive_process_fails_closed(self):
        with patch.dict(os.environ, {"DJANGO_ADMIN_PASSWORD": ""}):
            with patch(
                "backend.apps.accounts.management.commands.create_admin.sys.stdin",
                new=SimpleNamespace(isatty=lambda: False),
            ):
                with self.assertRaisesMessage(CommandError, "No interactive terminal"):
                    self.run_command()
        self.assertFalse(User.objects.exists())

    def test_interactive_password_is_confirmed_before_creation(self):
        secret = "Interactive-Safe-Admin-Passphrase-2026!"
        with patch.dict(os.environ, {"DJANGO_ADMIN_PASSWORD": ""}):
            with patch(
                "backend.apps.accounts.management.commands.create_admin.sys.stdin",
                new=SimpleNamespace(isatty=lambda: True),
            ):
                with patch(
                    "backend.apps.accounts.management.commands.create_admin.getpass.getpass",
                    side_effect=[secret, secret],
                ) as prompt:
                    output = StringIO()
                    self.run_command(stdout=output)

        self.assertEqual(prompt.call_count, 2)
        self.assertTrue(User.objects.get().check_password(secret))
        self.assertNotIn(secret, output.getvalue())

    def test_interactive_password_mismatch_does_not_create_account(self):
        with patch.dict(os.environ, {"DJANGO_ADMIN_PASSWORD": ""}):
            with patch(
                "backend.apps.accounts.management.commands.create_admin.sys.stdin",
                new=SimpleNamespace(isatty=lambda: True),
            ):
                with patch(
                    "backend.apps.accounts.management.commands.create_admin.getpass.getpass",
                    side_effect=["First-Safe-Passphrase-2026!", "Different-Safe-Passphrase-2026!"],
                ):
                    with self.assertRaisesMessage(CommandError, "do not match"):
                        self.run_command()
        self.assertFalse(User.objects.exists())

    def test_weak_password_is_rejected_without_echoing_it(self):
        secret = "password"
        output = StringIO()

        with patch.dict(os.environ, {"DJANGO_ADMIN_PASSWORD": secret}):
            with self.assertRaisesMessage(CommandError, "does not meet"):
                self.run_command(stdout=output)

        self.assertFalse(User.objects.exists())
        self.assertNotIn(secret, output.getvalue())


class AccountAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_token(self):
        response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrfToken", response.json())
        return response.json()["csrfToken"]

    def post_with_csrf(self, path, data, token):
        return self.client.post(
            path,
            data=data,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_csrf_token_is_http_only_and_me_requires_login(self):
        response = self.client.get("/api/v1/auth/csrf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertTrue(response.cookies["csrftoken"]["httponly"])
        self.assertEqual(response.cookies["csrftoken"]["samesite"], "Lax")

        me = self.client.get("/api/v1/me")
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me["Cache-Control"], "no-store")
        self.assertEqual(me.json()["error"]["code"], "not_authenticated")

    def test_register_requires_csrf_and_never_accepts_role_assignment(self):
        payload = {
            "email": "Player@Example.test",
            "password": "Str0ng-Unique-Passphrase-2026!",
            "displayName": "Player One",
        }
        rejected = self.client.post("/api/v1/auth/register", payload, format="json")
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["error"]["code"], "csrf_failed")

        token = self.csrf_token()
        elevated = self.post_with_csrf(
            "/api/v1/auth/register", {**payload, "role": "admin"}, token
        )
        self.assertEqual(elevated.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

        response = self.post_with_csrf("/api/v1/auth/register", payload, token)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], User.Roles.PARTICIPANT)
        self.assertEqual(response.json()["displayName"], "Player One")
        self.assertNotIn("password", response.json())
        self.assertEqual(User.objects.get().email, "player@example.test")

    def test_login_failure_is_generic_and_success_starts_private_session(self):
        user = User.objects.create_user(
            email="player@example.test",
            display_name="Player One",
            password="Str0ng-Unique-Passphrase-2026!",
        )
        User.objects.create_user(
            email="inactive@example.test",
            display_name="Inactive Player",
            password="Str0ng-Unique-Passphrase-2026!",
            is_active=False,
        )
        token = self.csrf_token()
        no_csrf = self.client.post(
            "/api/v1/auth/login",
            {"email": "player@example.test", "password": "Str0ng-Unique-Passphrase-2026!"},
            format="json",
        )
        self.assertEqual(no_csrf.status_code, 403)
        self.assertEqual(no_csrf.json()["error"]["code"], "csrf_failed")

        unknown = self.post_with_csrf(
            "/api/v1/auth/login",
            {"email": "nobody@example.test", "password": "Wrong-Passphrase-2026!"},
            token,
        )
        wrong_password = self.post_with_csrf(
            "/api/v1/auth/login",
            {"email": "PLAYER@example.test", "password": "Wrong-Passphrase-2026!"},
            token,
        )
        inactive = self.post_with_csrf(
            "/api/v1/auth/login",
            {"email": "inactive@example.test", "password": "Str0ng-Unique-Passphrase-2026!"},
            token,
        )
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(inactive.status_code, 401)
        self.assertEqual(unknown.json()["error"]["message"], wrong_password.json()["error"]["message"])
        self.assertEqual(unknown.json()["error"]["message"], inactive.json()["error"]["message"])

        login = self.post_with_csrf(
            "/api/v1/auth/login",
            {"email": "PLAYER@example.test", "password": "Str0ng-Unique-Passphrase-2026!"},
            token,
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["id"], str(user.id))
        self.assertEqual(login.json()["role"], User.Roles.PARTICIPANT)
        self.assertIn("csrfToken", login.json())
        self.assertTrue(self.client.cookies[settings.SESSION_COOKIE_NAME]["httponly"])
        self.assertEqual(login["Cache-Control"], "no-store")

        me = self.client.get("/api/v1/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["displayName"], "Player One")
        self.assertNotIn("email", me.json())
        self.assertEqual(me["Cache-Control"], "no-store")

        csrf_after_login = login.json()["csrfToken"]
        denied_logout = self.client.post("/api/v1/auth/logout", {}, format="json")
        self.assertEqual(denied_logout.status_code, 403)
        logout = self.post_with_csrf("/api/v1/auth/logout", {}, csrf_after_login)
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/me").status_code, 401)

    def test_cross_origin_registration_is_rejected(self):
        token = self.csrf_token()
        response = self.client.post(
            "/api/v1/auth/register",
            {
                "email": "attacker@example.test",
                "password": "Str0ng-Unique-Passphrase-2026!",
                "displayName": "Attacker",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://attacker.invalid",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "csrf_failed")
        self.assertFalse(User.objects.exists())

    def test_login_is_rate_limited(self):
        token = self.csrf_token()
        payload = {"email": "nobody@example.test", "password": "Wrong-Passphrase-2026!"}

        with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"auth_login": "1/minute"}):
            first = self.post_with_csrf("/api/v1/auth/login", payload, token)
            second = self.post_with_csrf("/api/v1/auth/login", payload, token)

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"]["code"], "throttled")

    def test_admin_permission_uses_application_role_and_active_state(self):
        participant = User.objects.create_user(
            email="participant@example.test",
            display_name="Participant",
            password="unused",
        )
        django_privileged_participant = User.objects.create_user(
            email="staff@example.test",
            display_name="Staff Participant",
            password="unused",
            is_staff=True,
            is_superuser=True,
        )
        admin = User.objects.create_user(
            email="admin@example.test",
            display_name="Application Admin",
            password="unused",
            role=User.Roles.ADMIN,
        )
        inactive_admin = User.objects.create_user(
            email="inactive-admin@example.test",
            display_name="Inactive Admin",
            password="unused",
            role=User.Roles.ADMIN,
            is_active=False,
        )

        def post_as(view, user=None):
            request = APIRequestFactory().post("/api/v1/admin/probe", {}, format="json")
            if user is not None:
                force_authenticate(request, user=user)
            return view.as_view()(request)

        self.assertEqual(post_as(_AdminMutationProbe).status_code, 401)
        self.assertEqual(post_as(_AdminMutationProbe, participant).status_code, 403)
        self.assertEqual(post_as(_AdminMutationProbe, django_privileged_participant).status_code, 403)
        self.assertEqual(post_as(_AdminMutationProbe, inactive_admin).status_code, 403)
        allowed = post_as(_AdminMutationProbe, admin)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data, {"changed": True})
        self.assertEqual(post_as(_ParticipantAccessProbe, participant).status_code, 200)
        self.assertEqual(post_as(_ParticipantAccessProbe, django_privileged_participant).status_code, 200)
        self.assertEqual(post_as(_ParticipantAccessProbe, admin).status_code, 403)

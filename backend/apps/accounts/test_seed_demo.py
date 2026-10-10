from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from backend.apps.accounts.models import User
from backend.apps.problems import compilers
from backend.apps.problems.models import ProblemVersion


class SeedDemoCommandTests(TestCase):
    @override_settings(DEBUG=True)
    def test_creates_admin_and_players_and_is_idempotent(self):
        call_command("seed_demo", stdout=StringIO())
        call_command("seed_demo", stdout=StringIO())

        self.assertEqual(User.objects.filter(role=User.Roles.ADMIN).count(), 1)
        self.assertEqual(User.objects.filter(role=User.Roles.PARTICIPANT).count(), 4)
        self.assertTrue(User.objects.get(email="player1@demo.local").check_password("player12345"))
        self.assertEqual(ProblemVersion.objects.count(), 1)

    @override_settings(DEBUG=False)
    def test_refuses_to_create_well_known_passwords_outside_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)


class VerifiedLanguagesSettingTests(TestCase):
    def test_languages_are_verified_only_when_the_operator_declares_them(self):
        with patch.dict("os.environ", {}, clear=False):
            self.assertEqual(compilers._verified_languages(), frozenset())
        with patch.dict("os.environ", {"SANDBOX_VERIFIED_LANGUAGES": " cpp20 , ,python3"}):
            self.assertEqual(compilers._verified_languages(), frozenset({"cpp20", "python3"}))

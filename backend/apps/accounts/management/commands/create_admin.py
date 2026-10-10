"""Create the first application administrator without granting Django superuser."""

import getpass
import hmac
import os
import sys

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from backend.apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the initial application admin using a protected password source."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Admin account email address.")
        parser.add_argument("--display-name", required=True, help="Admin display name.")

    def handle(self, *args, email, display_name, **options):
        password = os.environ.pop("DJANGO_ADMIN_PASSWORD", None) or None
        email, display_name = self._clean_identity(email, display_name)

        existing = User.objects.filter(email=email).first()
        if existing is not None:
            if existing.role != User.Roles.ADMIN:
                raise CommandError(
                    "An account already exists for this email and is not an application admin; "
                    "refusing to promote it."
                )
            if not existing.is_active:
                raise CommandError(
                    "The existing application admin is inactive; refusing to change its state."
                )
            self.stdout.write("Application admin already exists; account and password unchanged.")
            return

        password = password or self._prompt_password()
        candidate = User(email=email, display_name=display_name)
        if not password:
            raise CommandError("Admin password must not be empty.")
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError("Admin password does not meet the configured password policy.") from exc

        try:
            with transaction.atomic():
                User.objects.create_user(
                    email=email,
                    display_name=display_name,
                    password=password,
                    role=User.Roles.ADMIN,
                )
        except IntegrityError as exc:
            concurrent = User.objects.filter(email=email).first()
            if concurrent is not None and concurrent.role == User.Roles.ADMIN and concurrent.is_active:
                self.stdout.write("Application admin already exists; account and password unchanged.")
                return
            raise CommandError("Could not create the application admin account.") from exc

        self.stdout.write("Application admin created.")

    @staticmethod
    def _clean_identity(email, display_name):
        try:
            clean_email = User._meta.get_field("email").clean(email, None).casefold()
            clean_display_name = User._meta.get_field("display_name").clean(display_name, None)
        except ValidationError as exc:
            raise CommandError("Admin email or display name is invalid.") from exc
        return clean_email, clean_display_name

    @staticmethod
    def _prompt_password():
        if not sys.stdin.isatty():
            raise CommandError(
                "No interactive terminal; provide DJANGO_ADMIN_PASSWORD through a protected "
                "secret environment injection."
            )

        password = getpass.getpass("Admin password: ")
        confirmation = getpass.getpass("Confirm admin password: ")
        if not hmac.compare_digest(password, confirmation):
            raise CommandError("Admin passwords do not match.")
        return password

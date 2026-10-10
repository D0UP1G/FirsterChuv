"""Create local demo accounts and the demo problem so the platform can be tried in minutes."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from backend.apps.accounts.models import User

# Simple mock credentials for a local demo only; the command refuses to run with DJANGO_DEBUG=false.
DEMO_ACCOUNTS = (
    ("admin@demo.local", "Организатор", "admin12345", User.Roles.ADMIN),
    ("player1@demo.local", "Игрок 1", "player12345", User.Roles.PARTICIPANT),
    ("player2@demo.local", "Игрок 2", "player12345", User.Roles.PARTICIPANT),
    ("player3@demo.local", "Игрок 3", "player12345", User.Roles.PARTICIPANT),
    ("player4@demo.local", "Игрок 4", "player12345", User.Roles.PARTICIPANT),
)


class Command(BaseCommand):
    help = "Create demo accounts (admin and four players) and import the demo problem. Local use only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo creates accounts with well-known passwords and needs DJANGO_DEBUG=true.")
        for email, display_name, password, role in DEMO_ACCOUNTS:
            user, created = User.objects.get_or_create(
                email=email, defaults={"display_name": display_name, "role": role}
            )
            if created:
                user.set_password(password)
                user.save()
            self.stdout.write(f"{'created' if created else 'exists'} {email} ({role})")
        call_command("import_demo_problem", stdout=self.stdout)
        self.stdout.write("Demo ready: admin@demo.local / admin12345, player1..4@demo.local / player12345.")

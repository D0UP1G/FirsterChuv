from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Enable SQLite WAL mode before the API and worker processes start."

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("This command is only valid for the configured SQLite database.")

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode=WAL")
            mode = cursor.fetchone()[0]

        if str(mode).lower() != "wal":
            raise CommandError("SQLite refused WAL mode; API startup stopped.")

        timeout = settings.DATABASES["default"]["OPTIONS"]["timeout"]
        self.stdout.write(self.style.SUCCESS(f"SQLite WAL enabled; busy timeout is {timeout:g}s."))

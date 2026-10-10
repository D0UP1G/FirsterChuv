"""Run the lightweight independent match deadline reconciler."""

from __future__ import annotations

from time import sleep
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from django.utils import timezone

from backend.apps.competition.ledger_persistence import reconcile_match_run_deadline
from backend.apps.competition.models import MatchRun


MIN_INTERVAL_MS = 50
MAX_INTERVAL_MS = 60_000
DEFAULT_INTERVAL_MS = 250


def _interval_ms(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise CommandError("--interval-ms must be an integer") from error
    if not MIN_INTERVAL_MS <= parsed <= MAX_INTERVAL_MS:
        raise CommandError(
            f"--interval-ms must be between {MIN_INTERVAL_MS} and {MAX_INTERVAL_MS}"
        )
    return parsed


class Command(BaseCommand):
    help = "Reconcile expired current match clocks and drain FINALIZING runs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval-ms",
            type=_interval_ms,
            default=DEFAULT_INTERVAL_MS,
            help="Polling interval in milliseconds (50–60000).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one reconciliation pass and exit.",
        )

    def _reconcile_once(self, *, now) -> int:
        run_ids: list[UUID] = list(
            MatchRun.objects.filter(
                status=MatchRun.Status.RUNNING,
                started_at__isnull=False,
                match__current_run_id=F("pk"),
            ).order_by("started_at", "pk").values_list("pk", flat=True)
        )
        reconciled = 0
        for run_id in run_ids:
            run = reconcile_match_run_deadline(run_id, now=now)
            if run.status in (
                MatchRun.Status.FINALIZING,
                MatchRun.Status.FINISHED,
                MatchRun.Status.TIED,
            ):
                reconciled += 1
        return reconciled

    def handle(self, *args, **options):
        interval_ms = options["interval_ms"]
        run_once = options["once"]
        while True:
            reconciled = self._reconcile_once(now=timezone.now())
            if run_once or reconciled:
                self.stdout.write(f"Reconciled {reconciled} match run(s).")
            if run_once:
                return
            sleep(interval_ms / 1000)

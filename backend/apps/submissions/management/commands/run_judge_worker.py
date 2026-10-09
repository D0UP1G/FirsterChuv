"""Run the configured trusted judge worker."""

from __future__ import annotations

import math
from time import sleep

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from backend.apps.submissions.errors import IntegrationUnavailable
from backend.apps.submissions.factory import get_submission_worker
from backend.apps.submissions.services import MAX_LEASE_SECONDS


class Command(BaseCommand):
    help = "Run the configured durable submission and result worker."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process at most one queue item and exit.")
        parser.add_argument(
            "--max-jobs",
            type=int,
            default=None,
            help="Exit after processing this many queue items; by default the worker runs continuously.",
        )
        parser.add_argument("--idle-sleep", type=float, default=1.0, help="Seconds to wait when the queue is idle.")
        parser.add_argument("--lease-seconds", type=int, default=60, help="Bounded claim lease duration.")

    def handle(self, *args, **options):
        if options["max_jobs"] is not None and options["max_jobs"] <= 0:
            raise CommandError("--max-jobs must be a positive integer")
        if not math.isfinite(options["idle_sleep"]) or options["idle_sleep"] <= 0:
            raise CommandError("--idle-sleep must be a positive finite number")
        if not 0 < options["lease_seconds"] <= MAX_LEASE_SECONDS:
            raise CommandError(f"--lease-seconds must be between 1 and {MAX_LEASE_SECONDS}")

        try:
            worker = get_submission_worker()
        except IntegrationUnavailable as error:
            raise CommandError(str(error)) from error
        except Exception:
            raise CommandError(
                "submission worker runtime factory failed; configure valid real adapters"
            ) from None

        processed = 0
        while True:
            close_old_connections()
            try:
                iteration = worker.run_once(lease_seconds=options["lease_seconds"])
            except Exception:
                raise CommandError(
                    "submission worker stopped after an unexpected internal failure; active leases will be recovered"
                ) from None
            if iteration.did_work:
                processed += 1
                if options["verbosity"] >= 2:
                    self.stdout.write(iteration.action.value)
            elif options["once"]:
                if options["verbosity"] >= 2:
                    self.stdout.write(iteration.action.value)
                return
            else:
                sleep(options["idle_sleep"])

            if options["once"] or (
                options["max_jobs"] is not None and processed >= options["max_jobs"]
            ):
                return

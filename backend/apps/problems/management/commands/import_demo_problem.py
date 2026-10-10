"""Import a synthetic M0 demo or an internal normalized ProblemBundleV1 ZIP."""

from __future__ import annotations

import os
import stat

from django.core.management.base import BaseCommand, CommandError

from backend.apps.problems.archive import DEFAULT_ARCHIVE_POLICY
from backend.apps.problems.bundle import parse_problem_bundle
from backend.apps.problems.demo_bundle import build_demo_problem_archive
from backend.apps.problems.errors import ProblemBundleError, ProblemVersionConflict
from backend.apps.problems.storage import store_bundle


def _read_bounded_regular_file(path: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise CommandError("normalized bundle could not be opened as a regular file") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise CommandError("normalized bundle must be a regular file")
        if metadata.st_size <= 0 or metadata.st_size > DEFAULT_ARCHIVE_POLICY.max_archive_bytes:
            raise CommandError("normalized bundle is empty or exceeds the compressed-size limit")
        chunks = bytearray()
        while len(chunks) <= DEFAULT_ARCHIVE_POLICY.max_archive_bytes:
            chunk = os.read(
                descriptor,
                min(64 * 1024, DEFAULT_ARCHIVE_POLICY.max_archive_bytes + 1 - len(chunks)),
            )
            if not chunk:
                break
            chunks.extend(chunk)
        if len(chunks) > DEFAULT_ARCHIVE_POLICY.max_archive_bytes:
            raise CommandError("normalized bundle exceeds the compressed-size limit")
        return bytes(chunks)
    finally:
        os.close(descriptor)


class Command(BaseCommand):
    help = "Import the synthetic M0 problem or a normalized internal bundle ZIP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--archive",
            help="Path to an internal ProblemBundleV1 ZIP; omit to import the built-in synthetic demo.",
        )

    def handle(self, *args, **options):
        archive_bytes = (
            _read_bounded_regular_file(options["archive"])
            if options["archive"]
            else build_demo_problem_archive()
        )
        try:
            bundle = parse_problem_bundle(archive_bytes)
            version = store_bundle(bundle)
        except (ProblemBundleError, ProblemVersionConflict) as error:
            raise CommandError(f"normalized problem import failed: {error}") from error

        self.stdout.write(
            "Imported normalized problem "
            f"{version.problem_id} version={version.version} checksum={version.checksum} "
            f"readiness={version.readiness} active={str(version.is_active).lower()}"
        )

from dataclasses import replace
from io import StringIO
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import zlib

from django.core.management import call_command, CommandError
from django.test import TestCase

from backend.apps.problems.bundle import parse_problem_bundle
from backend.apps.problems.catalog import DjangoProblemCatalog
from backend.apps.problems.compilers import COMPILERS
from backend.apps.problems.demo_bundle import build_demo_problem_archive
from backend.apps.problems.models import (
    ProblemPrivateArtifact,
    ProblemPublicAsset,
    ProblemPublicData,
    ProblemTestCase,
    ProblemVersion,
)
from backend.apps.problems.storage import store_bundle


class ImportDemoProblemCommandTests(TestCase):
    def test_imports_programmatic_demo_idempotently_and_keeps_private_data_separate(self):
        expected = parse_problem_bundle(build_demo_problem_archive())
        first_output, second_output = StringIO(), StringIO()

        call_command("import_demo_problem", stdout=first_output)
        call_command("import_demo_problem", stdout=second_output)

        self.assertEqual(ProblemVersion.objects.count(), 1)
        version = ProblemVersion.objects.get()
        self.assertEqual(version.problem_id, expected.problem_id)
        self.assertEqual(version.version, expected.version)
        self.assertEqual(version.checksum, expected.checksum)
        self.assertEqual(version.readiness, ProblemVersion.Readiness.NOT_READY)
        self.assertFalse(version.is_active)
        self.assertEqual(first_output.getvalue(), second_output.getvalue())

        public = ProblemPublicData.objects.get(version=version)
        self.assertIn("$a+b$", public.statement_markdown)
        self.assertIn("| Вход | Выход |", public.statement_markdown)
        self.assertIn(f"/api/v1/problem-assets/{expected.assets[0].asset_id}", public.statement_markdown)
        self.assertEqual(
            public.examples,
            [{"input": "2 3\n", "output": "5\n"}, {"input": "10 -4\n", "output": "6\n"}],
        )
        self.assertEqual(public.time_limit_ms, 2000)
        self.assertEqual(public.memory_limit_bytes, 536870912)
        self.assertEqual(ProblemPublicAsset.objects.filter(public_data=public).count(), 1)
        self.assertEqual(
            ProblemTestCase.objects.filter(private_data__version=version).count(),
            2,
        )
        self.assertEqual(
            ProblemPrivateArtifact.objects.filter(private_data__version=version).values_list("role", flat=True).get(),
            ProblemPrivateArtifact.Role.REFERENCE,
        )
        self.assertFalse(COMPILERS["cpp20"].verified)

        image = expected.assets[0].contents
        offset = 8
        while offset < len(image):
            size = struct.unpack(">I", image[offset:offset + 4])[0]
            chunk_type = image[offset + 4:offset + 8]
            chunk_data = image[offset + 8:offset + 8 + size]
            crc = struct.unpack(">I", image[offset + 8 + size:offset + 12 + size])[0]
            self.assertEqual(crc, zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF)
            offset += 12 + size
        self.assertEqual(offset, len(image))

    def test_public_projection_keeps_private_tests_and_reference_out(self):
        call_command("import_demo_problem", stdout=StringIO())
        test_compilers = {"cpp20": replace(COMPILERS["cpp20"], verified=True)}
        store_bundle(
            parse_problem_bundle(build_demo_problem_archive()),
            compiler_registry=test_compilers,
        )
        (public,) = DjangoProblemCatalog(compiler_registry=test_compilers).describe_ready(
            [ProblemVersion.objects.get().problem_id]
        )

        self.assertEqual(len(public.asset_ids), 1)
        self.assertEqual(len(public.examples), 2)
        self.assertFalse(hasattr(public, "tests"))
        self.assertFalse(hasattr(public, "private_artifacts"))
        self.assertFalse(hasattr(public, "checksum"))

    def test_imports_an_explicit_normalized_archive_with_bounded_regular_file_read(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "normalized.zip"
            path.write_bytes(build_demo_problem_archive())

            output = StringIO()
            call_command("import_demo_problem", archive=str(path), stdout=output)

        self.assertEqual(ProblemVersion.objects.count(), 1)
        self.assertIn("readiness=NOT_READY", output.getvalue())

    def test_rejects_non_regular_archive_path(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(CommandError, "regular file"):
                call_command("import_demo_problem", archive=directory)

    def test_rejects_oversized_archive_before_reading_contents(self):
        from backend.apps.problems.archive import DEFAULT_ARCHIVE_POLICY

        with TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.zip"
            with path.open("wb") as archive:
                archive.truncate(DEFAULT_ARCHIVE_POLICY.max_archive_bytes + 1)

            with self.assertRaisesRegex(CommandError, "compressed-size limit"):
                call_command("import_demo_problem", archive=str(path))

from dataclasses import replace

from django.test import TestCase

from backend.apps.problems.bundle import parse_problem_bundle
from backend.apps.problems.catalog import DjangoProblemCatalog
from backend.apps.problems.compilers import COMPILERS
from backend.apps.problems.errors import ProblemNotReady, ProblemVersionConflict
from backend.apps.problems.models import ProblemPrivateData, ProblemTestCase, ProblemVersion
from backend.apps.problems.storage import store_bundle
from backend.apps.problems.tests.bundle_fixtures import make_bundle_archive, normalized_manifest

TEST_VERIFIED_COMPILERS = {"cpp20": replace(COMPILERS["cpp20"], verified=True)}


class ProblemCatalogTests(TestCase):
    def test_store_is_idempotent_and_public_catalog_does_not_return_private_data(self) -> None:
        bundle = parse_problem_bundle(make_bundle_archive())
        first = store_bundle(bundle, compiler_registry=TEST_VERIFIED_COMPILERS)
        repeated = store_bundle(bundle, compiler_registry=TEST_VERIFIED_COMPILERS)
        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(first.readiness, ProblemVersion.Readiness.READY)
        self.assertTrue(first.is_active)

        with self.assertRaises(ProblemNotReady):
            DjangoProblemCatalog().describe_ready([bundle.problem_id])
        catalog = DjangoProblemCatalog(compiler_registry=TEST_VERIFIED_COMPILERS)
        described = catalog.describe_ready([bundle.problem_id])
        self.assertEqual(len(described), 1)
        self.assertEqual(described[0].version, "synthetic-v1")
        self.assertFalse(hasattr(described[0], "tests"))
        self.assertFalse(hasattr(described[0], "checksum"))
        self.assertEqual(ProblemPrivateData.objects.count(), 1)
        self.assertEqual(ProblemTestCase.objects.count(), 1)
        first.version = "mutated"
        with self.assertRaises(ValueError):
            first.save()

        loaded = catalog.load_bundle(bundle.problem_id, bundle.version)
        self.assertEqual(loaded.tests, bundle.tests)
        self.assertEqual(loaded.private_artifacts, bundle.private_artifacts)

    def test_same_problem_version_cannot_be_replaced_with_different_checksum(self) -> None:
        first = parse_problem_bundle(make_bundle_archive())
        changed = parse_problem_bundle(
            make_bundle_archive(files={"private/tests/001.out": b"different\n"})
        )
        store_bundle(first, compiler_registry=TEST_VERIFIED_COMPILERS)
        with self.assertRaises(ProblemVersionConflict):
            store_bundle(changed, compiler_registry=TEST_VERIFIED_COMPILERS)

    def test_not_ready_versions_are_never_described_or_loaded(self) -> None:
        bundle = parse_problem_bundle(make_bundle_archive(manifest=normalized_manifest(with_private=False)))
        record = store_bundle(bundle)
        self.assertEqual(record.readiness, ProblemVersion.Readiness.NOT_READY)
        self.assertFalse(record.is_active)
        with self.assertRaises(ProblemNotReady):
            DjangoProblemCatalog().describe_ready([bundle.problem_id])
        with self.assertRaises(ProblemNotReady):
            DjangoProblemCatalog().load_bundle(bundle.problem_id, bundle.version)

    def test_private_version_is_not_implicitly_selected_over_existing_active_one(self) -> None:
        active = parse_problem_bundle(make_bundle_archive())
        store_bundle(active, compiler_registry=TEST_VERIFIED_COMPILERS)
        next_manifest = normalized_manifest()
        next_manifest["version"] = "synthetic-v2"
        next_bundle = parse_problem_bundle(make_bundle_archive(manifest=next_manifest))
        record = store_bundle(next_bundle, compiler_registry=TEST_VERIFIED_COMPILERS)
        self.assertFalse(record.is_active)
        catalog = DjangoProblemCatalog(compiler_registry=TEST_VERIFIED_COMPILERS)
        self.assertEqual(catalog.describe_ready([active.problem_id])[0].version, "synthetic-v1")

    def test_unverified_compiler_keeps_complete_bundle_not_ready(self) -> None:
        bundle = parse_problem_bundle(make_bundle_archive())
        self.assertTrue(bundle.has_complete_judge_data)
        record = store_bundle(bundle)
        self.assertEqual(record.readiness, ProblemVersion.Readiness.NOT_READY)
        self.assertFalse(record.is_active)

    def test_same_checksum_can_become_ready_after_compiler_verification(self) -> None:
        bundle = parse_problem_bundle(make_bundle_archive())
        stored = store_bundle(bundle)
        self.assertEqual(stored.readiness, ProblemVersion.Readiness.NOT_READY)
        verified = store_bundle(bundle, compiler_registry=TEST_VERIFIED_COMPILERS)
        self.assertEqual(verified.pk, stored.pk)
        self.assertEqual(verified.readiness, ProblemVersion.Readiness.READY)
        self.assertTrue(verified.is_active)

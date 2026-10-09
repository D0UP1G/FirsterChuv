from django.test import SimpleTestCase

from backend.apps.problems.bundle import parse_problem_bundle
from backend.apps.problems.errors import ProblemBundleError
from backend.apps.problems.tests.bundle_fixtures import PNG_BYTES, make_bundle_archive, normalized_manifest


class NormalizedBundleTests(SimpleTestCase):
    def test_parses_ready_synthetic_bundle_and_separates_public_projection(self) -> None:
        bundle = parse_problem_bundle(make_bundle_archive())
        self.assertTrue(bundle.has_complete_judge_data)
        self.assertEqual(bundle.languages[0].id, "cpp20")
        self.assertEqual(bundle.languages[0].name, "C++20")
        self.assertEqual(bundle.assets[0].contents, PNG_BYTES)
        self.assertEqual(bundle.tests[0].input, b"1 2\n")
        self.assertEqual(bundle.private_artifacts[0].role, "reference")
        public = bundle.public_projection()
        self.assertFalse(hasattr(public, "tests"))
        self.assertFalse(hasattr(public, "private_artifacts"))
        self.assertEqual(public.asset_ids, ("figure",))

    def test_missing_private_data_is_retained_as_not_ready(self) -> None:
        bundle = parse_problem_bundle(make_bundle_archive(manifest=normalized_manifest(with_private=False)))
        self.assertFalse(bundle.has_complete_judge_data)
        self.assertEqual(bundle.tests, ())

    def test_custom_checker_allows_tests_without_expected_output(self) -> None:
        manifest = normalized_manifest()
        manifest["private"]["tests"][0]["expectedOutputPath"] = None
        manifest["private"]["checkerPath"] = "private/checkers/checker.cpp"
        manifest["private"]["checkerLanguageId"] = "cpp20"
        bundle = parse_problem_bundle(make_bundle_archive(manifest=manifest, files={"private/checkers/checker.cpp": b"// synthetic"}))
        self.assertTrue(bundle.has_complete_judge_data)
        self.assertIsNone(bundle.tests[0].expected_output)
        reference = next(item for item in bundle.private_artifacts if item.role == "reference")
        self.assertEqual(reference.source_path, "private/references/reference.cpp")

    def test_custom_checker_without_registered_language_keeps_bundle_not_ready(self) -> None:
        manifest = normalized_manifest()
        manifest["private"]["tests"][0]["expectedOutputPath"] = None
        manifest["private"]["checkerPath"] = "private/checkers/checker.cpp"
        bundle = parse_problem_bundle(
            make_bundle_archive(manifest=manifest, files={"private/checkers/checker.cpp": b"// synthetic"})
        )
        self.assertFalse(bundle.has_complete_judge_data)

    def test_checksum_is_stable_across_zip_entry_order_and_covers_private_files(self) -> None:
        first = parse_problem_bundle(make_bundle_archive())
        reverse_order = tuple(reversed((
            "manifest.json",
            "public/assets/figure.png",
            "private/tests/001.in",
            "private/tests/001.out",
            "private/references/reference.cpp",
        )))
        second = parse_problem_bundle(make_bundle_archive(order=reverse_order))
        changed_private = parse_problem_bundle(
            make_bundle_archive(files={"private/tests/001.out": b"changed\n"})
        )
        self.assertEqual(first.checksum, second.checksum)
        self.assertNotEqual(first.checksum, changed_private.checksum)

    def test_rejects_unknown_compilers_limits_and_asset_type_mismatch(self) -> None:
        manifest = normalized_manifest()
        manifest["public"]["languages"] = [{"id": "unknown"}]
        with self.assertRaises(ProblemBundleError):
            parse_problem_bundle(make_bundle_archive(manifest=manifest))

        manifest = normalized_manifest()
        manifest["public"]["limits"]["timeLimitMs"] = True
        with self.assertRaises(ProblemBundleError):
            parse_problem_bundle(make_bundle_archive(manifest=manifest))

        manifest = normalized_manifest()
        manifest["public"]["assets"][0]["mediaType"] = "image/svg+xml"
        with self.assertRaises(ProblemBundleError):
            parse_problem_bundle(make_bundle_archive(manifest=manifest))

        with self.assertRaises(ProblemBundleError):
            parse_problem_bundle(
                make_bundle_archive(files={"public/assets/figure.png": b"<html>active content</html>"})
            )

    def test_rejects_duplicate_json_keys_and_private_paths_in_public_assets(self) -> None:
        with self.assertRaises(ProblemBundleError):
            parse_problem_bundle(make_bundle_archive(manifest_bytes=b'{"schemaVersion":1,"schemaVersion":1}'))

        manifest = normalized_manifest()
        manifest["public"]["assets"][0]["path"] = "private/tests/001.in"
        with self.assertRaises(ProblemBundleError):
            parse_problem_bundle(make_bundle_archive(manifest=manifest))

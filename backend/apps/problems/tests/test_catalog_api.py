from dataclasses import replace

from django.test import TestCase
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.problems.bundle import parse_problem_bundle
from backend.apps.problems.compilers import COMPILERS
from backend.apps.problems.storage import store_bundle
from backend.apps.problems.tests.bundle_fixtures import make_bundle_archive, normalized_manifest


TEST_VERIFIED_COMPILERS = {"cpp20": replace(COMPILERS["cpp20"], verified=True)}


class AdminProblemVersionListApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient(enforce_csrf_checks=True)
        self.admin = User.objects.create_user(
            email="problem-admin@example.test",
            display_name="Problem Admin",
            password="test-password",
            role=User.Roles.ADMIN,
            is_staff=False,
            is_superuser=False,
        )
        self.participant = User.objects.create_user(
            email="problem-participant@example.test",
            display_name="Problem Participant",
            password="test-password",
            is_staff=True,
        )

    def test_only_active_application_admin_can_list_problem_versions(self) -> None:
        anonymous = self.client.get("/api/v1/problems")
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous["Cache-Control"], "no-store")

        self.client.force_login(self.participant)
        participant = self.client.get("/api/v1/problems")
        self.assertEqual(participant.status_code, 403)
        self.assertEqual(participant["Cache-Control"], "no-store")

        inactive_admin = User.objects.create_user(
            email="inactive-problem-admin@example.test",
            display_name="Inactive Problem Admin",
            password="test-password",
            role=User.Roles.ADMIN,
            is_active=False,
        )
        self.client.force_login(inactive_admin)
        inactive = self.client.get("/api/v1/problems")
        self.assertEqual(inactive.status_code, 401)

    def test_lists_ready_and_not_ready_versions_without_private_data(self) -> None:
        ready_manifest = normalized_manifest()
        ready_manifest["version"] = "ready-v1"
        ready = parse_problem_bundle(make_bundle_archive(manifest=ready_manifest))
        store_bundle(ready, compiler_registry=TEST_VERIFIED_COMPILERS)

        not_ready_manifest = normalized_manifest(with_private=False)
        not_ready_manifest["version"] = "not-ready-v2"
        not_ready = parse_problem_bundle(make_bundle_archive(manifest=not_ready_manifest))
        store_bundle(not_ready)

        self.client.force_login(self.admin)
        response = self.client.get("/api/v1/problems")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        versions = {item["version"]: item for item in payload["results"]}
        self.assertEqual(versions["ready-v1"]["readiness"], "READY")
        self.assertTrue(versions["ready-v1"]["isActive"])
        self.assertEqual(versions["not-ready-v2"]["readiness"], "NOT_READY")
        self.assertFalse(versions["not-ready-v2"]["isActive"])
        self.assertEqual(versions["ready-v1"]["languages"][0]["id"], "cpp20")
        self.assertFalse(
            {"checksum", "tests", "privateArtifacts", "statementMarkdown"}
            & set(versions["ready-v1"])
        )

    def test_limit_offset_pagination_returns_requested_page(self) -> None:
        for version in ("one", "two", "three"):
            manifest = normalized_manifest(with_private=False)
            manifest["version"] = version
            store_bundle(parse_problem_bundle(make_bundle_archive(manifest=manifest)))

        self.client.force_login(self.admin)
        response = self.client.get("/api/v1/problems?limit=1&offset=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(len(payload["results"]), 1)
        self.assertIsNotNone(payload["next"])

    def test_requested_page_size_is_capped_at_one_hundred(self) -> None:
        for index in range(101):
            manifest = normalized_manifest(with_private=False)
            manifest["version"] = f"version-{index:03}"
            store_bundle(parse_problem_bundle(make_bundle_archive(manifest=manifest)))

        self.client.force_login(self.admin)
        response = self.client.get("/api/v1/problems?limit=500")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 101)
        self.assertEqual(len(response.json()["results"]), 100)
        self.assertIsNotNone(response.json()["next"])

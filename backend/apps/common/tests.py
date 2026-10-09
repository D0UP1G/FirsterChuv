import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints
from uuid import UUID, uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import NotAuthenticated

from backend.apps.common.api import CamelCaseJSONRenderer, exception_handler
from backend.apps.common.contracts import (
    AttemptReceipt,
    InfrastructureFailureReceipt,
    InfrastructureFailureSink,
    ResultReceipt,
    RunProblemSnapshot,
    RunProblemSnapshotProvider,
    SubmissionPermit,
)


class APIContractTests(TestCase):
    def test_common_ports_import_without_optional_domain_apps(self):
        repository_root = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            [sys.executable, str(repository_root / "scripts/check_contract_imports.py")],
            cwd=repository_root,
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("without optional domain apps", result.stdout)

    def test_health_is_minimal_and_correlatable(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
        self.assertTrue(response["X-Request-ID"])
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertNotIn("secret", response.content.decode().lower())

    def test_error_envelope_uses_camel_case_request_id(self):
        request = SimpleNamespace(request_id=uuid4())
        view = SimpleNamespace(get_authenticate_header=lambda request: None)

        response = exception_handler(NotAuthenticated(), {"request": request, "view": view})
        payload = json.loads(CamelCaseJSONRenderer().render(response.data))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(payload["error"]["code"], "not_authenticated")
        self.assertEqual(payload["requestId"], str(request.request_id))
        self.assertNotIn("request_id", payload)

    @override_settings(DEBUG=True)
    def test_missing_api_route_does_not_redirect_for_trailing_slash(self):
        for path in ("/api/v1", "/api/v1/unknown/"):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["error"]["code"], "not_found")
                self.assertIn("requestId", response.json())
                self.assertNotIn("Location", response)


class SharedTypedPortTests(TestCase):
    def test_new_provider_and_sink_signatures_use_common_dtos(self):
        failure_hints = get_type_hints(InfrastructureFailureSink.record_infrastructure_failure)
        snapshot_hints = get_type_hints(RunProblemSnapshotProvider.resolve)

        self.assertIs(failure_hints["receipt"], InfrastructureFailureReceipt)
        self.assertIs(failure_hints["return"], type(None))
        self.assertIs(snapshot_hints["run_id"], UUID)
        self.assertIs(snapshot_hints["problem_id"], UUID)
        self.assertIs(snapshot_hints["return"], RunProblemSnapshot)

    def test_infrastructure_failure_receipt_is_frozen_and_additive(self):
        receipt = InfrastructureFailureReceipt(
            submission_id=uuid4(),
            run_id=uuid4(),
            reason_code="worker_lease_expired",
            retryable=False,
        )

        self.assertEqual(
            tuple(field.name for field in fields(receipt)),
            ("submission_id", "run_id", "reason_code", "retryable"),
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(receipt, "reason_code", "private diagnostics")

    def test_run_problem_snapshot_is_frozen_and_run_scoped(self):
        snapshot = RunProblemSnapshot(
            run_id=uuid4(),
            problem_id=uuid4(),
            problem_version="2026-10",
            problem_checksum="a" * 64,
        )

        self.assertEqual(
            tuple(field.name for field in fields(snapshot)),
            ("run_id", "problem_id", "problem_version", "problem_checksum"),
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(snapshot, "problem_checksum", "b" * 64)

    def test_existing_v1_receipt_fields_remain_unchanged(self):
        self.assertEqual(
            tuple(field.name for field in fields(SubmissionPermit)),
            ("run_id", "elapsed_ms", "scoring_version"),
        )
        self.assertEqual(
            tuple(field.name for field in fields(AttemptReceipt)),
            (
                "submission_id",
                "run_id",
                "user_id",
                "problem_id",
                "received_at",
                "elapsed_ms",
                "scoring_version",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(ResultReceipt)),
            (
                "submission_id",
                "run_id",
                "user_id",
                "problem_id",
                "received_at",
                "elapsed_ms",
                "scoring_version",
                "verdict",
            ),
        )

from dataclasses import replace
from unittest.mock import patch

from django.test import SimpleTestCase

from backend.apps.problems import compilers
from backend.apps.problems.compilers import COMPILERS
from backend.apps.submissions.api_runtime import (
    AdmissionEventWriter,
    VerifiedLanguageRegistry,
    build_submission_service,
)
from backend.apps.submissions.factory import get_submission_service


class ApiRuntimeWiringTests(SimpleTestCase):
    def test_language_is_supported_only_when_its_compiler_is_verified(self):
        registry = VerifiedLanguageRegistry()
        self.assertFalse(registry.is_supported("cpp20"))
        self.assertFalse(registry.is_supported("unknown"))
        with patch.object(compilers, "COMPILERS", {"cpp20": replace(COMPILERS["cpp20"], verified=True)}):
            self.assertTrue(registry.is_supported("cpp20"))

    def test_admission_event_writer_drops_only_the_unpublished_private_event(self):
        writer = AdmissionEventWriter()
        writer.append("match:1", "submission.accepted", {"userId": "private"})
        with self.assertRaises(ValueError):
            writer.append("match:1", "score.changed", {})

    def test_production_settings_wire_a_service_with_real_ports(self):
        service = get_submission_service()
        self.assertIsNotNone(service.competition)
        self.assertIsNotNone(service.event_writer)
        self.assertIsNotNone(service.language_registry)
        self.assertEqual(type(build_submission_service()), type(service))

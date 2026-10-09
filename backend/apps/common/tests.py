import json
from types import SimpleNamespace
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import NotAuthenticated

from backend.apps.common.api import CamelCaseJSONRenderer, exception_handler


class APIContractTests(TestCase):
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

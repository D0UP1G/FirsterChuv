from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.submissions.models import Submission
from backend.apps.submissions.services import SubmissionService
from backend.apps.submissions.tests.test_services import (
    FakeCompetition,
    FakeEventWriter,
    FakeLanguageRegistry,
)


class SubmissionAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.author = User.objects.create_user("author@example.test", "Author", "passphrase")
        self.other = User.objects.create_user("other@example.test", "Other", "passphrase")
        self.admin = User.objects.create_superuser("admin@example.test", "Admin", "passphrase")
        self.match_id = uuid4()
        self.run_id = uuid4()
        self.problem_id = uuid4()
        self.service = SubmissionService(
            competition=FakeCompetition(),
            event_writer=FakeEventWriter(),
            language_registry=FakeLanguageRegistry(),
        )
        self.client.force_login(self.author)
        self.csrf_token = self.client.get("/api/v1/auth/csrf").json()["csrfToken"]

    def post_submission(self, *, source="int main() { return 0; }", key="attempt-1", extra=None):
        body = {
            "runId": str(self.run_id),
            "problemId": str(self.problem_id),
            "languageId": "cpp20",
            "source": source,
            **(extra or {}),
        }
        return self.client.post(
            f"/api/v1/matches/{self.match_id}/submissions",
            body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def test_submission_http_response_contains_only_accepted_public_metadata(self):
        with patch("backend.apps.submissions.views.get_submission_service", return_value=self.service):
            response = self.post_submission()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], Submission.Status.QUEUED)
        self.assertEqual(response.json()["elapsedMs"], 37)
        self.assertNotIn("source", response.json())
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(Submission.objects.count(), 1)

    def test_default_runtime_fails_closed_and_does_not_store_source(self):
        response = self.post_submission()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "integration_unavailable")
        self.assertEqual(Submission.objects.count(), 0)

    def test_author_only_detail_and_source_routes_hide_another_users_submission(self):
        accepted = self.service.admit(
            actor_id=self.author.pk,
            match_id=self.match_id,
            run_id=self.run_id,
            problem_id=self.problem_id,
            language_id="cpp20",
            source="private source",
            idempotency_key="attempt-1",
        )
        with patch("backend.apps.submissions.views.get_submission_service", return_value=self.service):
            self.client.force_login(self.other)
            detail = self.client.get(f"/api/v1/submissions/{accepted.id}")
            source = self.client.get(f"/api/v1/submissions/{accepted.id}/source")
            self.assertEqual(detail.status_code, 404)
            self.assertEqual(source.status_code, 404)
            self.client.force_login(self.author)
            own_source = self.client.get(f"/api/v1/submissions/{accepted.id}/source")

        self.assertEqual(own_source.status_code, 200)
        self.assertEqual(own_source.json()["source"], "private source")
        self.assertEqual(own_source["Cache-Control"], "no-store")

    def test_match_history_contains_only_authenticated_authors_submissions(self):
        self.service.admit(
            actor_id=self.author.pk,
            match_id=self.match_id,
            run_id=self.run_id,
            problem_id=self.problem_id,
            language_id="cpp20",
            source="private source",
            idempotency_key="author-attempt",
        )
        self.service.admit(
            actor_id=self.other.pk,
            match_id=self.match_id,
            run_id=self.run_id,
            problem_id=self.problem_id,
            language_id="cpp20",
            source="other private source",
            idempotency_key="other-attempt",
        )
        with patch("backend.apps.submissions.views.get_submission_service", return_value=self.service):
            response = self.client.get(f"/api/v1/matches/{self.match_id}/submissions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertNotIn("source", response.json()["results"][0])

    def test_admin_cannot_submit_and_unknown_client_fields_are_rejected(self):
        self.client.force_login(self.admin)
        denied = self.post_submission()
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.author)
        unknown = self.post_submission(extra={"receivedAt": "2026-10-09T12:00:00Z"})
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(Submission.objects.count(), 0)

    def test_changed_request_under_same_key_returns_conflict(self):
        with patch("backend.apps.submissions.views.get_submission_service", return_value=self.service):
            accepted = self.post_submission()
            conflict = self.post_submission(source="int main() { return 1; }")

        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["error"]["code"], "idempotency_conflict")

    def test_submit_rate_is_bounded_per_author_and_match(self):
        with patch("backend.apps.submissions.views.get_submission_service", return_value=self.service):
            for _ in range(30):
                response = self.post_submission()
                self.assertEqual(response.status_code, 202)
            limited = self.post_submission()

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["error"]["code"], "throttled")

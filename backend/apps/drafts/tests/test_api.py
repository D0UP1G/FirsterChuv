from uuid import UUID, uuid4
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from backend.apps.accounts.models import User
from backend.apps.common.contracts import WorkspaceContext
from backend.apps.drafts.errors import WorkspaceDenied
from backend.apps.drafts.services import DraftService


class FakeWorkspaceAccess:
    """Test-only A2 workspace adapter with an explicit private membership."""

    def __init__(self, *, actor_id, match_id, run_id, problem_id):
        self.actor_id = actor_id
        self.match_id = match_id
        self.run_id = run_id
        self.problem_id = problem_id

    def authorize_workspace(self, actor_id, match_id, run_id, problem_id, purpose):
        if (actor_id, match_id, run_id, problem_id) != (
            self.actor_id,
            self.match_id,
            self.run_id,
            self.problem_id,
        ):
            raise WorkspaceDenied("workspace is not available")
        if purpose != "draft":
            raise WorkspaceDenied("workspace purpose is not available")
        return WorkspaceContext(
            actor_id,
            run_id,
            problem_id,
            frozenset({"read_draft", "write_draft"}),
            condition_available=False,
        )


class DraftAPITests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.author = User.objects.create_user("author@example.test", "Author", "passphrase")
        self.other = User.objects.create_user("other@example.test", "Other", "passphrase")
        self.admin = User.objects.create_superuser("admin@example.test", "Admin", "passphrase")
        self.match_id = uuid4()
        self.run_id = uuid4()
        self.problem_id = uuid4()
        self.access = FakeWorkspaceAccess(
            actor_id=self.author.pk,
            match_id=self.match_id,
            run_id=self.run_id,
            problem_id=self.problem_id,
        )
        self.client.force_login(self.author)
        self.csrf_token = self.client.get("/api/v1/auth/csrf").json()["csrfToken"]
        self.path = f"/api/v1/matches/{self.match_id}/problems/{self.problem_id}/draft"
        self.query = {"runId": str(self.run_id), "languageId": "cpp20"}

    def get_draft(self):
        return self.client.get(self.path, self.query)

    def put_draft(self, *, source, expected_revision, use_csrf=True, extra=None):
        body = {
            "runId": str(self.run_id),
            "source": source,
            "expectedRevision": expected_revision,
            **(extra or {}),
        }
        headers = {"HTTP_X_CSRFTOKEN": self.csrf_token} if use_csrf else {}
        return self.client.put(
            f"{self.path}?languageId=cpp20",
            body,
            format="json",
            **headers,
        )

    def test_get_and_put_follow_draft_v1_and_responses_are_private(self):
        with patch("backend.apps.drafts.views.get_workspace_access", return_value=self.access):
            blank = self.get_draft()
            saved = self.put_draft(source="int main() { return 0; }", expected_revision=0)
            current = self.get_draft()

        self.assertEqual(blank.status_code, 404)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual((saved.json()["source"], saved.json()["revision"]), ("int main() { return 0; }", 1))
        self.assertEqual(current.json()["source"], "int main() { return 0; }")
        self.assertEqual(current["Cache-Control"], "no-store")
        self.assertEqual(current["Referrer-Policy"], "no-referrer")
        self.assertNotIn("actorId", current.json())

    def test_revision_conflict_returns_server_revision_and_preserves_server_and_local_versions(self):
        local_version = "local version from the editor"
        with patch("backend.apps.drafts.views.get_workspace_access", return_value=self.access):
            self.put_draft(source="server version", expected_revision=0)
            conflict = self.put_draft(source=local_version, expected_revision=0)
            current = self.get_draft()

        self.assertEqual(conflict.status_code, 409)
        current_draft = conflict.json()["error"]["fields"]["currentDraft"]
        self.assertEqual(current_draft["revision"], 1)
        self.assertEqual(current_draft["source"], "server version")
        self.assertEqual(current.json()["source"], "server version")
        self.assertEqual(local_version, "local version from the editor")

    def test_conflict_without_a_saved_draft_does_not_fabricate_a_revision(self):
        with patch("backend.apps.drafts.views.get_workspace_access", return_value=self.access):
            conflict = self.put_draft(source="local version", expected_revision=2)

        self.assertEqual(conflict.status_code, 409)
        self.assertIsNone(conflict.json()["error"]["fields"]["currentDraft"])

    def test_exhausted_sqlite_contention_is_a_retryable_503(self):
        with (
            patch("backend.apps.drafts.views.get_workspace_access", return_value=self.access),
            patch.object(DraftService, "_save_once", side_effect=OperationalError("database is locked")) as save_once,
            patch("backend.apps.drafts.services.sleep"),
        ):
            response = self.put_draft(source="local source", expected_revision=0)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "draft_busy")
        self.assertNotIn("database is locked", str(response.json()))
        self.assertEqual(save_once.call_count, 3)

    @override_settings(WORKSPACE_ACCESS_FACTORY=None)
    def test_missing_workspace_port_fails_closed(self):
        response = self.get_draft()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "workspace_unavailable")

    def test_author_idor_admin_and_inactive_account_are_denied(self):
        with patch("backend.apps.drafts.views.get_workspace_access", return_value=self.access):
            self.put_draft(source="private source", expected_revision=0)
            self.client.force_login(self.other)
            other = self.get_draft()
            self.client.force_login(self.admin)
            admin = self.get_draft()
            self.author.is_active = False
            self.author.save(update_fields=("is_active",))
            self.client.force_login(self.author)
            inactive = self.get_draft()

        self.assertEqual(other.status_code, 404)
        self.assertEqual(admin.status_code, 403)
        self.assertEqual(inactive.status_code, 401)

    def test_put_requires_csrf_and_rejects_unknown_fields(self):
        with patch("backend.apps.drafts.views.get_workspace_access", return_value=self.access):
            no_csrf = self.put_draft(source="source", expected_revision=0, use_csrf=False)
            unknown = self.put_draft(source="source", expected_revision=0, extra={"role": "admin"})

        self.assertEqual(no_csrf.status_code, 403)
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(
            DraftService.history(
                context=WorkspaceContext(
                    self.author.pk,
                    self.run_id,
                    self.problem_id,
                    frozenset({"read_history"}),
                    condition_available=False,
                ),
                language_id="cpp20",
            ),
            [],
        )

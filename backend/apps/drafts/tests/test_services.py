from uuid import UUID, uuid4

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.common.contracts import WorkspaceContext
from backend.apps.drafts.errors import DraftError, DraftRevisionConflict
from backend.apps.drafts.services import DraftService


def authorized_context(user_id, run_id, problem_id, actions):
    return WorkspaceContext(user_id, run_id, problem_id, frozenset(actions), condition_available=False)


class DraftServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("author@example.test", "Author", "passphrase")
        self.run_id = uuid4()
        self.problem_id = uuid4()
        self.draft_context = authorized_context(
            self.user.pk,
            self.run_id,
            self.problem_id,
            {"read_draft", "write_draft"},
        )
        self.history_context = authorized_context(
            self.user.pk,
            self.run_id,
            self.problem_id,
            {"read_history"},
        )

    def test_draft_round_trips_across_revision_updates_and_history_is_private(self):
        initial = DraftService.get_current(context=self.draft_context, language_id="cpp20")
        self.assertIsNone(initial)

        saved = DraftService.save(
            context=self.draft_context,
            language_id="cpp20",
            source="int main() { return 0; }",
            expected_revision=0,
        )
        updated = DraftService.save(
            context=self.draft_context,
            language_id="cpp20",
            source="int main() { return 1; }",
            expected_revision=1,
        )

        self.assertEqual((saved.revision, updated.revision), (1, 2))
        self.assertEqual(DraftService.get_current(context=self.draft_context, language_id="cpp20"), updated)
        history = DraftService.history(context=self.history_context, language_id="cpp20")
        self.assertEqual([item.revision for item in history], [1, 2])
        self.assertEqual([item.source for item in history], [saved.source, updated.source])

    def test_revision_conflict_returns_current_server_version_without_overwriting(self):
        current = DraftService.save(
            context=self.draft_context,
            language_id="cpp20",
            source="server version",
            expected_revision=0,
        )
        local_version = "local version from another tab"

        with self.assertRaises(DraftRevisionConflict) as raised:
            DraftService.save(
                context=self.draft_context,
                language_id="cpp20",
                source=local_version,
                expected_revision=0,
            )

        self.assertEqual(raised.exception.current, current)
        self.assertEqual(DraftService.get_current(context=self.draft_context, language_id="cpp20"), current)
        self.assertNotEqual(local_version, raised.exception.current.source)

    def test_repeating_the_current_source_does_not_create_an_extra_revision(self):
        saved = DraftService.save(
            context=self.draft_context,
            language_id="cpp20",
            source="same source",
            expected_revision=0,
        )
        repeated = DraftService.save(
            context=self.draft_context,
            language_id="cpp20",
            source="same source",
            expected_revision=1,
        )

        self.assertEqual(saved, repeated)
        self.assertEqual(len(DraftService.history(context=self.history_context, language_id="cpp20")), 1)

    def test_language_and_run_are_part_of_the_private_draft_namespace(self):
        cpp_draft = DraftService.save(
            context=self.draft_context,
            language_id="cpp20",
            source="cpp source",
            expected_revision=0,
        )
        python_draft = DraftService.save(
            context=self.draft_context,
            language_id="python3",
            source="python source",
            expected_revision=0,
        )
        other_run = authorized_context(
            self.user.pk,
            uuid4(),
            self.problem_id,
            {"read_draft", "write_draft"},
        )
        other_run_draft = DraftService.save(
            context=other_run,
            language_id="cpp20",
            source="other run source",
            expected_revision=0,
        )

        self.assertEqual((cpp_draft.source, python_draft.source), ("cpp source", "python source"))
        self.assertEqual(DraftService.get_current(context=other_run, language_id="cpp20"), other_run_draft)
        self.assertEqual(DraftService.get_current(context=self.draft_context, language_id="cpp20"), cpp_draft)

    def test_storage_rejects_missing_authorization_and_history_scope(self):
        unauthorized_context = authorized_context(
            self.user.pk,
            self.run_id,
            self.problem_id,
            set(),
        )
        with self.assertRaises(DraftError):
            DraftService.get_current(context=unauthorized_context, language_id="cpp20")
        with self.assertRaises(DraftError):
            DraftService.history(context=self.draft_context, language_id="cpp20")

    def test_read_and_write_require_distinct_contract_actions(self):
        read_only = authorized_context(self.user.pk, self.run_id, self.problem_id, {"read_draft"})
        write_only = authorized_context(self.user.pk, self.run_id, self.problem_id, {"write_draft"})

        self.assertIsNone(DraftService.get_current(context=read_only, language_id="cpp20"))
        with self.assertRaises(DraftError):
            DraftService.save(
                context=read_only,
                language_id="cpp20",
                source="source",
                expected_revision=0,
            )
        with self.assertRaises(DraftError):
            DraftService.get_current(context=write_only, language_id="cpp20")

    def test_source_size_language_and_revision_are_validated(self):
        with self.assertRaises(DraftError):
            DraftService.save(
                context=self.draft_context,
                language_id="cpp20",
                source="x" * (32 * 1024 + 1),
                expected_revision=0,
            )
        with self.assertRaises(DraftError):
            DraftService.get_current(context=self.draft_context, language_id="../source")
        with self.assertRaises(DraftError):
            DraftService.save(
                context=self.draft_context,
                language_id="cpp20",
                source="source",
                expected_revision=True,
            )

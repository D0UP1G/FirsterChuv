"""File-backed SQLite coverage for concurrent private draft saves."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from unittest.mock import patch
from uuid import uuid4

from django.db import close_old_connections, connection, connections
from django.db.models.query import QuerySet
from django.test import TransactionTestCase

from backend.apps.accounts.models import User
from backend.apps.common.contracts import WorkspaceContext
from backend.apps.drafts.errors import DraftRevisionConflict
from backend.apps.drafts.models import Draft, DraftRevision
from backend.apps.drafts.services import DraftService


class DraftCASConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        super().setUp()
        if connection.vendor != "sqlite":
            self.skipTest("draft CAS contention checks are specific to SQLite")
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            database_name = cursor.fetchone()[2]
        if not database_name or database_name == ":memory:":
            self.skipTest("run with --settings=backend.apps.drafts.test_settings for file-backed SQLite")

        self.user = User.objects.create_user("draft-race@example.test", "Draft race", "passphrase")
        self.run_id = uuid4()
        self.problem_id = uuid4()
        self.context = WorkspaceContext(
            self.user.pk,
            self.run_id,
            self.problem_id,
            frozenset({"read_draft", "write_draft"}),
            condition_available=False,
        )

    def _save_concurrently(self, *, sources, expected_revision, synchronize_on):
        barrier = Barrier(len(sources))
        thread_state = local()
        original = getattr(QuerySet, synchronize_on)

        def synchronize_same_read(queryset, *args, **kwargs):
            if queryset.model is Draft and not getattr(thread_state, "waited", False):
                thread_state.waited = True
                barrier.wait(timeout=10)
            return original(queryset, *args, **kwargs)

        def save(source):
            close_old_connections()
            try:
                try:
                    snapshot = DraftService.save(
                        context=self.context,
                        language_id="cpp20",
                        source=source,
                        expected_revision=expected_revision,
                    )
                except DraftRevisionConflict as error:
                    return "conflict", error.current
                return "saved", snapshot
            finally:
                connections.close_all()

        with patch.object(QuerySet, synchronize_on, new=synchronize_same_read):
            with ThreadPoolExecutor(max_workers=len(sources)) as executor:
                futures = [executor.submit(save, source) for source in sources]
                return [future.result(timeout=20) for future in futures]

    def _assert_one_winner(self, results, *, sources, first_source=None):
        self.assertCountEqual([status for status, _ in results], ["saved", "conflict"])
        saved = next(value for status, value in results if status == "saved")
        conflict = next(value for status, value in results if status == "conflict")
        current = DraftService.get_current(context=self.context, language_id="cpp20")
        history = DraftService.history(
            context=WorkspaceContext(
                self.user.pk,
                self.run_id,
                self.problem_id,
                frozenset({"read_history"}),
                condition_available=False,
            ),
            language_id="cpp20",
        )

        self.assertEqual(current, saved)
        self.assertIn(current.source, sources)
        for attempted_source, (status, _) in zip(sources, results):
            if status == "conflict":
                self.assertNotEqual(attempted_source, current.source)
        self.assertEqual(Draft.objects.count(), 1)
        self.assertEqual([item.source for item in history], ([first_source] if first_source else []) + [current.source])
        self.assertEqual([item.revision for item in history], list(range(1, len(history) + 1)))
        return current, conflict, history

    def test_simultaneous_first_puts_return_one_save_and_one_revision_conflict(self):
        sources = ["first tab source", "second tab source"]
        results = self._save_concurrently(
            sources=sources,
            expected_revision=0,
            synchronize_on="create",
        )

        current, conflict, history = self._assert_one_winner(results, sources=sources)
        self.assertEqual(current.revision, 1)
        self.assertEqual(conflict, current)
        self.assertEqual(len(history), 1)

    def test_simultaneous_updates_return_one_save_and_preserve_the_other_tab(self):
        initial = DraftService.save(
            context=self.context,
            language_id="cpp20",
            source="initial source",
            expected_revision=0,
        )
        sources = ["first tab update", "second tab update"]
        results = self._save_concurrently(
            sources=sources,
            expected_revision=initial.revision,
            synchronize_on="update",
        )

        current, conflict, history = self._assert_one_winner(
            results,
            sources=sources,
            first_source=initial.source,
        )
        self.assertEqual(current.revision, initial.revision + 1)
        self.assertEqual(conflict, current)
        self.assertEqual(len(history), 2)

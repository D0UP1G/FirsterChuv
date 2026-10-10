"""File-backed SQLite admission race and rollback coverage."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from unittest.mock import patch
from uuid import uuid4

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.submissions.errors import QueueFull
from backend.apps.submissions.models import QueueCounter, Submission
from backend.apps.submissions.ports import SubmissionPermit
from backend.apps.submissions.services import SubmissionService, _acquire_admission_write_intent


class DatabaseCompetition:
    """Test-only ports that write ledger rows in the admission transaction."""

    def authorize_submission(self, actor_id, match_id, run_id, problem_id, received_at):
        return SubmissionPermit(run_id=run_id, elapsed_ms=73, scoring_version="race-test-v1")

    def register_accepted(self, receipt):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO test_submission_accepted (submission_id, received_at) VALUES (%s, %s)",
                [str(receipt.submission_id), receipt.received_at.isoformat()],
            )


class DatabaseEventWriter:
    def __init__(self, *, fail_after_write=False):
        self.fail_after_write = fail_after_write

    def append(self, scope, event_type, public_payload):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO test_submission_events (scope, event_type, payload) VALUES (%s, %s, %s)",
                [scope, event_type, json.dumps(public_payload, sort_keys=True)],
            )
        if self.fail_after_write:
            raise RuntimeError("test event failure after write")


class DatabaseLanguageRegistry:
    def is_supported(self, language_id):
        return language_id == "cpp20"


class SubmissionAdmissionConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE test_submission_accepted "
                "(submission_id varchar(36) PRIMARY KEY, received_at varchar(64) NOT NULL)"
            )
            cursor.execute(
                "CREATE TABLE test_submission_events "
                "(id integer PRIMARY KEY AUTOINCREMENT, scope varchar(128) NOT NULL, "
                "event_type varchar(64) NOT NULL, payload text NOT NULL)"
            )

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE test_submission_events")
            cursor.execute("DROP TABLE test_submission_accepted")
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM test_submission_events")
            cursor.execute("DELETE FROM test_submission_accepted")
        self.users = [
            User.objects.create_user("race-a@example.test", "Race A", "passphrase"),
            User.objects.create_user("race-b@example.test", "Race B", "passphrase"),
        ]
        self.match_id = uuid4()
        self.run_id = uuid4()
        self.problem_id = uuid4()
        self.received_at = timezone.now()

    def make_service(self, *, max_pending_global=10, event_writer=None):
        return SubmissionService(
            competition=DatabaseCompetition(),
            event_writer=event_writer or DatabaseEventWriter(),
            language_registry=DatabaseLanguageRegistry(),
            max_pending_global=max_pending_global,
            max_pending_per_user=10,
            max_pending_per_match=20,
        )

    def submit_concurrently(self, specs, *, service):
        barrier = Barrier(len(specs))

        def submit(spec):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return service.admit(
                    actor_id=spec["actor_id"],
                    match_id=self.match_id,
                    run_id=self.run_id,
                    problem_id=self.problem_id,
                    language_id="cpp20",
                    source="int main() { return 0; }",
                    idempotency_key=spec["key"],
                    received_at=self.received_at,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(specs)) as executor:
            futures = [executor.submit(submit, spec) for spec in specs]
            results = []
            for future in futures:
                try:
                    results.append(future.result(timeout=20))
                except QueueFull as error:
                    results.append(error)
        return results

    def count_test_rows(self, table):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            return cursor.fetchone()[0]

    def test_database_is_file_backed_for_transaction_race_checks(self):
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            database_name = cursor.fetchone()[2]
        if not database_name or database_name == ":memory:":
            self.skipTest(
                "run this suite with --settings=backend.apps.submissions.test_settings for file-backed SQLite"
            )
        self.assertNotIn(":memory:", database_name)

    def test_concurrent_different_keys_are_both_admitted_once(self):
        results = self.submit_concurrently(
            [
                {"actor_id": self.users[0].pk, "key": "different-a"},
                {"actor_id": self.users[1].pk, "key": "different-b"},
            ],
            service=self.make_service(),
        )

        self.assertEqual(len({item.id for item in results}), 2)
        self.assertEqual(Submission.objects.count(), 2)
        self.assertEqual(self.count_test_rows("test_submission_accepted"), 2)
        self.assertEqual(self.count_test_rows("test_submission_events"), 2)
        self.assertEqual(QueueCounter.objects.get(scope_key="global").pending_count, 2)
        self.assertTrue(all(item.received_at == self.received_at for item in results))

    def test_concurrent_same_key_returns_one_submission_and_one_receipt_and_event(self):
        first_write_barrier = Barrier(2)
        calls_lock = Lock()
        calls = 0

        def synchronized_write_intent():
            nonlocal calls
            with calls_lock:
                calls += 1
                call_number = calls
            if call_number <= 2:
                first_write_barrier.wait(timeout=10)
            return _acquire_admission_write_intent()

        with patch(
            "backend.apps.submissions.services._acquire_admission_write_intent",
            side_effect=synchronized_write_intent,
        ):
            results = self.submit_concurrently(
                [
                    {"actor_id": self.users[0].pk, "key": "same-key"},
                    {"actor_id": self.users[0].pk, "key": "same-key"},
                ],
                service=self.make_service(),
            )

        self.assertEqual(calls, 2)
        self.assertEqual(results[0].id, results[1].id)
        self.assertEqual(results[0].received_at, self.received_at)
        self.assertEqual(results[1].received_at, self.received_at)
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(self.count_test_rows("test_submission_accepted"), 1)
        self.assertEqual(self.count_test_rows("test_submission_events"), 1)
        self.assertEqual(QueueCounter.objects.get(scope_key="global").pending_count, 1)

    def test_concurrent_capacity_limit_rejects_excess_without_partial_reservation(self):
        results = self.submit_concurrently(
            [
                {"actor_id": self.users[0].pk, "key": "cap-a"},
                {"actor_id": self.users[1].pk, "key": "cap-b"},
            ],
            service=self.make_service(max_pending_global=1),
        )

        self.assertEqual(sum(isinstance(item, QueueFull) for item in results), 1)
        self.assertEqual(sum(not isinstance(item, QueueFull) for item in results), 1)
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(self.count_test_rows("test_submission_accepted"), 1)
        self.assertEqual(self.count_test_rows("test_submission_events"), 1)
        counters = {item.scope_key: item.pending_count for item in QueueCounter.objects.all()}
        self.assertEqual(counters["global"], 1)
        self.assertEqual(counters[f"match:{self.match_id}"], 1)
        self.assertEqual(sum(value for key, value in counters.items() if key.startswith("actor:")), 1)

    def test_event_failure_rolls_back_capacity_submission_accepted_ledger_and_event(self):
        service = self.make_service(event_writer=DatabaseEventWriter(fail_after_write=True))
        with self.assertRaisesRegex(RuntimeError, "test event failure"):
            service.admit(
                actor_id=self.users[0].pk,
                match_id=self.match_id,
                run_id=self.run_id,
                problem_id=self.problem_id,
                language_id="cpp20",
                source="int main() { return 0; }",
                idempotency_key="rollback-key",
                received_at=self.received_at,
            )

        self.assertEqual(Submission.objects.count(), 0)
        self.assertEqual(QueueCounter.objects.count(), 0)
        self.assertEqual(self.count_test_rows("test_submission_accepted"), 0)
        self.assertEqual(self.count_test_rows("test_submission_events"), 0)

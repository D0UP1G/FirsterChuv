from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.db import OperationalError, close_old_connections, connection
from django.test import TransactionTestCase

from backend.apps.events.models import MatchSnapshot
from backend.apps.events.services import (
    PublicSnapshotBusy,
    PublicSnapshotConflict,
    read_snapshot,
    save_snapshot,
)


def _public_payload(display_name="Player A"):
    first = str(uuid4())
    second = str(uuid4())
    problem = str(uuid4())
    return {
        "leaderUserId": None,
        "players": [
            {
                "userId": first,
                "displayName": display_name,
                "solvedCount": 0,
                "penaltyMs": 0,
                "lastAcceptedElapsedMs": None,
                "tasks": [
                    {
                        "problemId": problem,
                        "label": "A",
                        "status": "NOT_STARTED",
                        "attempts": 0,
                        "lastVerdict": None,
                    }
                ],
            },
            {
                "userId": second,
                "displayName": "Player B",
                "solvedCount": 0,
                "penaltyMs": 0,
                "lastAcceptedElapsedMs": None,
                "tasks": [
                    {
                        "problemId": problem,
                        "label": "A",
                        "status": "NOT_STARTED",
                        "attempts": 0,
                        "lastVerdict": None,
                    }
                ],
            },
        ],
    }


class FileBackedSnapshotConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        super().setUp()
        self.match_id = uuid4()
        self.run_id = uuid4()
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            database_path = cursor.fetchone()[2]
        self.assertEqual(connection.vendor, "sqlite")
        if not database_path:
            self.skipTest(
                "Run this suite with DJANGO_SETTINGS_MODULE=backend.apps.events.test_settings"
            )

    def _parallel_save(self, barrier, *, run_id, cursor_id, payload):
        close_old_connections()
        connection.ensure_connection()
        connection_id = id(connection.connection)
        try:
            barrier.wait(timeout=5)
            saved = save_snapshot(
                match_id=self.match_id,
                run_id=run_id,
                last_event_id=cursor_id,
                public_payload=payload,
            )
            return connection_id, saved
        finally:
            connection.close()

    def _run_pair(self, operations):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self._parallel_save, barrier, **operation)
                for operation in operations
            ]
            return [future.result(timeout=10) for future in futures]

    def test_parallel_first_create_uses_distinct_connections_and_keeps_one_row(self):
        payload = _public_payload()
        results = self._run_pair(
            [
                {"run_id": self.run_id, "cursor_id": 7, "payload": payload},
                {"run_id": self.run_id, "cursor_id": 7, "payload": payload},
            ]
        )

        self.assertNotEqual(results[0][0], results[1][0])
        self.assertEqual([result for _connection_id, result in results], [True, True])
        self.assertEqual(MatchSnapshot.objects.filter(pk=self.match_id).count(), 1)
        self.assertEqual(read_snapshot(match_id=self.match_id)["lastEventId"], 7)

    def test_parallel_update_never_replaces_a_newer_cursor(self):
        initial = _public_payload()
        save_snapshot(
            match_id=self.match_id,
            run_id=self.run_id,
            last_event_id=2,
            public_payload=initial,
        )
        results = self._run_pair(
            [
                {"run_id": self.run_id, "cursor_id": 4, "payload": _public_payload("Cursor 4")},
                {"run_id": self.run_id, "cursor_id": 3, "payload": _public_payload("Cursor 3")},
            ]
        )

        self.assertNotEqual(results[0][0], results[1][0])
        snapshot = read_snapshot(match_id=self.match_id)
        self.assertEqual(snapshot["lastEventId"], 4)
        self.assertEqual(snapshot["payload"]["players"][0]["displayName"], "Cursor 4")

    def test_file_backed_stale_cursor_is_ignored_and_identical_equal_cursor_is_noop(self):
        payload = _public_payload("Current")
        self.assertTrue(
            save_snapshot(
                match_id=self.match_id,
                run_id=self.run_id,
                last_event_id=5,
                public_payload=payload,
            )
        )

        self.assertFalse(
            save_snapshot(
                match_id=self.match_id,
                run_id=self.run_id,
                last_event_id=4,
                public_payload=_public_payload("Stale"),
            )
        )
        self.assertTrue(
            save_snapshot(
                match_id=self.match_id,
                run_id=self.run_id,
                last_event_id=5,
                public_payload=payload,
            )
        )
        with self.assertRaises(PublicSnapshotConflict):
            save_snapshot(
                match_id=self.match_id,
                run_id=uuid4(),
                last_event_id=5,
                public_payload=payload,
            )

        stored = read_snapshot(match_id=self.match_id)
        self.assertEqual(stored["lastEventId"], 5)
        self.assertEqual(stored["runId"], str(self.run_id))
        self.assertEqual(stored["payload"], payload)

    def test_parallel_equal_cursor_conflict_cannot_overwrite_winner(self):
        payloads = (_public_payload("First writer"), _public_payload("Second writer"))
        barrier = Barrier(2)

        def save_or_conflict(payload):
            close_old_connections()
            connection.ensure_connection()
            connection_id = id(connection.connection)
            try:
                barrier.wait(timeout=5)
                save_snapshot(
                    match_id=self.match_id,
                    run_id=self.run_id,
                    last_event_id=9,
                    public_payload=payload,
                )
                return connection_id, "saved"
            except PublicSnapshotConflict:
                return connection_id, "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(save_or_conflict, payload) for payload in payloads]
            results = [future.result(timeout=10) for future in futures]

        self.assertNotEqual(results[0][0], results[1][0])
        self.assertCountEqual([result for _connection_id, result in results], ["saved", "conflict"])
        stored = read_snapshot(match_id=self.match_id)
        self.assertIn(stored["payload"], payloads)

    def test_exhausted_sqlite_busy_is_reported_after_bounded_full_retries(self):
        with (
            patch(
                "backend.apps.events.services._save_snapshot_once",
                side_effect=OperationalError("database is locked"),
            ) as write,
            patch("backend.apps.events.services.time.sleep"),
        ):
            with self.assertRaises(PublicSnapshotBusy):
                save_snapshot(
                    match_id=self.match_id,
                    run_id=self.run_id,
                    last_event_id=1,
                    public_payload=_public_payload(),
                )

        self.assertEqual(write.call_count, 3)

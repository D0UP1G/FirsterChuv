from copy import deepcopy
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import TestCase

from backend.apps.events.models import MatchEvent
from backend.apps.events.public_payloads import PublicEventInputError
from backend.apps.events.services import (
    append_event,
    current_event_cursor,
    read_events_after,
)


class PublicEventStoreTests(TestCase):
    def setUp(self):
        self.tournament_id = uuid4()
        self.other_tournament_id = uuid4()
        self.match_id = uuid4()
        self.run_id = uuid4()
        self.users = (uuid4(), uuid4())
        self.problems = (uuid4(), uuid4())

    def score_payload(self):
        return {
            "leaderUserId": str(self.users[0]),
            "players": [
                {
                    "userId": str(self.users[0]),
                    "displayName": "Игрок A",
                    "solvedCount": 1,
                    "penaltyMs": 180_000,
                    "lastAcceptedElapsedMs": 120_000,
                    "tasks": [
                        {
                            "problemId": str(self.problems[0]),
                            "label": "A",
                            "status": "SOLVED",
                            "attempts": 2,
                            "lastVerdict": "OK",
                        },
                        {
                            "problemId": str(self.problems[1]),
                            "label": "B",
                            "status": "ATTEMPTED",
                            "attempts": 1,
                            "lastVerdict": "WA",
                        },
                    ],
                },
                {
                    "userId": str(self.users[1]),
                    "displayName": "Игрок B",
                    "solvedCount": 0,
                    "penaltyMs": 0,
                    "lastAcceptedElapsedMs": None,
                    "tasks": [
                        {
                            "problemId": str(self.problems[0]),
                            "label": "A",
                            "status": "NOT_STARTED",
                            "attempts": 0,
                            "lastVerdict": None,
                        },
                        {
                            "problemId": str(self.problems[1]),
                            "label": "B",
                            "status": "NOT_STARTED",
                            "attempts": 0,
                            "lastVerdict": None,
                        },
                    ],
                },
            ],
        }

    def append_score(self, *, tournament_id=None, payload=None):
        return append_event(
            tournament_id=tournament_id or self.tournament_id,
            match_id=self.match_id,
            run_id=self.run_id,
            event_type=MatchEvent.Types.SCORE_CHANGED,
            public_payload=payload if payload is not None else self.score_payload(),
        )

    def test_public_envelope_matches_score_event_v1(self):
        event_id = self.append_score()

        [event] = read_events_after(tournament_id=self.tournament_id)

        self.assertEqual(event_id, event["eventId"])
        self.assertEqual(event["type"], "score.changed")
        self.assertEqual(event["matchId"], str(self.match_id))
        self.assertEqual(event["runId"], str(self.run_id))
        self.assertEqual(event["payload"], self.score_payload())
        self.assertEqual(current_event_cursor(tournament_id=self.tournament_id), event_id)

    def test_event_ids_are_monotonic_and_cursor_read_is_tournament_scoped(self):
        first = self.append_score()
        _other = self.append_score(tournament_id=self.other_tournament_id)
        third = self.append_score()

        events = read_events_after(tournament_id=self.tournament_id)
        after_first = read_events_after(
            tournament_id=self.tournament_id,
            after_event_id=first,
        )

        self.assertLess(first, third)
        self.assertEqual([event["eventId"] for event in events], [first, third])
        self.assertEqual([event["eventId"] for event in after_first], [third])
        self.assertEqual(current_event_cursor(tournament_id=self.other_tournament_id), _other)

    def test_cursor_page_is_bounded_and_input_is_validated(self):
        self.append_score()
        self.append_score()

        with self.assertRaisesRegex(PublicEventInputError, "after_event_id"):
            read_events_after(tournament_id=self.tournament_id, after_event_id=True)
        with self.assertRaisesRegex(PublicEventInputError, "limit"):
            read_events_after(tournament_id=self.tournament_id, limit=251)
        with self.assertRaisesRegex(PublicEventInputError, "limit"):
            read_events_after(tournament_id=self.tournament_id, limit=0)
        self.assertEqual(len(read_events_after(tournament_id=self.tournament_id, limit=1)), 1)

    def test_unknown_or_not_yet_typed_event_type_is_rejected(self):
        with self.assertRaisesRegex(PublicEventInputError, "not supported"):
            append_event(
                tournament_id=self.tournament_id,
                match_id=self.match_id,
                run_id=self.run_id,
                event_type="submission.accepted",
                public_payload={},
            )

    def test_database_constraint_rejects_untyped_public_event_types(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MatchEvent.objects.create(
                    tournament_id=self.tournament_id,
                    match_id=self.match_id,
                    run_id=self.run_id,
                    event_type="submission.accepted",
                    payload={},
                )

    def test_replay_fails_closed_on_directly_inserted_private_payload(self):
        MatchEvent.objects.create(
            tournament_id=self.tournament_id,
            match_id=self.match_id,
            run_id=self.run_id,
            event_type=MatchEvent.Types.SCORE_CHANGED,
            payload={"source": "private code"},
        )

        with self.assertRaisesRegex(PublicEventInputError, "keys mismatch"):
            read_events_after(tournament_id=self.tournament_id)
        with self.assertRaisesRegex(PublicEventInputError, "not supported"):
            append_event(
                tournament_id=self.tournament_id,
                match_id=self.match_id,
                run_id=self.run_id,
                event_type="private.source",
                public_payload={},
            )

    def test_private_and_unknown_fields_are_rejected_at_every_level(self):
        payload = self.score_payload()
        payload["email"] = "private@example.test"
        with self.assertRaisesRegex(PublicEventInputError, "keys mismatch"):
            self.append_score(payload=payload)

        payload = self.score_payload()
        payload["players"][0]["source"] = "private code"
        with self.assertRaisesRegex(PublicEventInputError, "keys mismatch"):
            self.append_score(payload=payload)

        payload = self.score_payload()
        payload["players"][0]["tasks"][0]["compilerLog"] = "private diagnostic"
        with self.assertRaisesRegex(PublicEventInputError, "keys mismatch"):
            self.append_score(payload=payload)

        self.assertEqual(MatchEvent.objects.count(), 0)

    def test_inconsistent_score_payload_is_rejected(self):
        payload = self.score_payload()
        payload["players"][0]["solvedCount"] = 0
        with self.assertRaisesRegex(PublicEventInputError, "solvedCount"):
            self.append_score(payload=payload)

        payload = self.score_payload()
        payload["leaderUserId"] = str(uuid4())
        with self.assertRaisesRegex(PublicEventInputError, "one of the match players"):
            self.append_score(payload=payload)

    def test_invalid_event_does_not_create_a_row_and_caller_rollback_removes_valid_event(self):
        payload = self.score_payload()
        payload["players"][0]["tasks"][0]["status"] = "WINNER"
        with self.assertRaises(PublicEventInputError):
            self.append_score(payload=payload)
        self.assertEqual(MatchEvent.objects.count(), 0)

        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with transaction.atomic():
                self.append_score()
                raise RuntimeError("rollback")
        self.assertEqual(MatchEvent.objects.count(), 0)

    def test_validation_copies_payload_before_storing(self):
        payload = self.score_payload()
        stored_expected = deepcopy(payload)
        self.append_score(payload=payload)
        payload["players"][0]["displayName"] = "changed after append"

        [event] = read_events_after(tournament_id=self.tournament_id)

        self.assertEqual(event["payload"], stored_expected)

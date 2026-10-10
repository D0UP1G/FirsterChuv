from datetime import datetime, timedelta, timezone
import unittest

from backend.apps.competition.domain.clock import (
    ClockError,
    ClockRunStatus,
    ClockSnapshot,
    active_elapsed_ms,
    pause_clock,
    reconcile_deadline,
    resume_clock,
    start_clock,
    submission_elapsed_ms,
)
from backend.apps.competition.domain.start_policy import (
    MatchStartState,
    StartMode,
    StartPolicyError,
    mark_player_ready,
)


START = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)


def ready_clock(*, duration_ms: int = 60_000) -> ClockSnapshot:
    return ClockSnapshot(
        status=ClockRunStatus.READY,
        allowed_duration_ms=duration_ms,
    )


class MatchClockTests(unittest.TestCase):
    def test_start_is_server_authoritative_and_only_allowed_once(self) -> None:
        running = start_clock(ready_clock(), START)

        self.assertEqual(running.status, ClockRunStatus.RUNNING)
        self.assertEqual(running.started_at, START)
        with self.assertRaises(ClockError):
            start_clock(running, START + timedelta(seconds=1))

    def test_waiting_and_ready_runs_have_no_elapsed_time(self) -> None:
        self.assertEqual(active_elapsed_ms(ready_clock(), START), 0)
        waiting = ClockSnapshot(
            status=ClockRunStatus.WAITING,
            allowed_duration_ms=60_000,
        )
        self.assertEqual(active_elapsed_ms(waiting, START), 0)

    def test_submission_returns_server_elapsed_before_deadline(self) -> None:
        running = start_clock(ready_clock(), START)

        self.assertEqual(
            submission_elapsed_ms(running, START + timedelta(milliseconds=12_345)),
            12_345,
        )

    def test_exact_deadline_is_closed(self) -> None:
        running = start_clock(ready_clock(duration_ms=10_000), START)

        with self.assertRaisesRegex(ClockError, "deadline"):
            submission_elapsed_ms(running, START + timedelta(seconds=10))

    def test_submission_is_closed_while_paused(self) -> None:
        running = start_clock(ready_clock(), START)
        paused = pause_clock(running, START + timedelta(seconds=5))

        with self.assertRaisesRegex(ClockError, "RUNNING"):
            submission_elapsed_ms(paused, START + timedelta(hours=1))
        self.assertEqual(active_elapsed_ms(paused, START + timedelta(hours=1)), 5_000)

    def test_pause_cannot_extend_the_clock_past_deadline(self) -> None:
        running = start_clock(ready_clock(duration_ms=5_000), START)

        with self.assertRaisesRegex(ClockError, "deadline"):
            pause_clock(running, START + timedelta(seconds=5))

    def test_pause_and_resume_preserve_active_elapsed_time(self) -> None:
        running = start_clock(ready_clock(), START)
        paused = pause_clock(running, START + timedelta(seconds=7))
        resumed_at = START + timedelta(seconds=27)
        resumed = resume_clock(paused, resumed_at)

        self.assertEqual(paused.accumulated_pause_ms, 0)
        self.assertEqual(resumed.accumulated_pause_ms, 20_000)
        self.assertEqual(active_elapsed_ms(resumed, resumed_at), 7_000)
        self.assertEqual(
            active_elapsed_ms(resumed, resumed_at + timedelta(seconds=3)),
            10_000,
        )

    def test_reconcile_transitions_at_deadline_and_is_idempotent(self) -> None:
        running = start_clock(ready_clock(duration_ms=5_000), START)

        self.assertEqual(
            reconcile_deadline(running, START + timedelta(milliseconds=4_999)),
            running,
        )
        finalizing = reconcile_deadline(running, START + timedelta(seconds=5))
        self.assertEqual(finalizing.status, ClockRunStatus.FINALIZING)
        self.assertEqual(
            reconcile_deadline(finalizing, START + timedelta(seconds=6)),
            finalizing,
        )

    def test_paused_run_is_not_finalized_by_clock_tick(self) -> None:
        running = start_clock(ready_clock(duration_ms=1_000), START)
        paused = pause_clock(running, START + timedelta(milliseconds=500))

        self.assertEqual(
            reconcile_deadline(paused, START + timedelta(days=1)),
            paused,
        )

    def test_invalid_naive_timestamp_is_rejected(self) -> None:
        running = start_clock(ready_clock(), START)

        with self.assertRaisesRegex(ClockError, "timezone-aware"):
            active_elapsed_ms(running, datetime(2026, 10, 9, 10, 1))

    def test_clock_cannot_move_backwards(self) -> None:
        running = start_clock(ready_clock(), START)

        with self.assertRaisesRegex(ClockError, "backwards"):
            active_elapsed_ms(running, START - timedelta(milliseconds=1))

    def test_invalid_duration_and_pause_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ClockError, "positive integer"):
            ready_clock(duration_ms=0)
        with self.assertRaisesRegex(ClockError, "paused_at"):
            ClockSnapshot(
                status=ClockRunStatus.PAUSED,
                allowed_duration_ms=1_000,
                started_at=START,
            )
        with self.assertRaisesRegex(ClockError, "backwards"):
            ClockSnapshot(
                status=ClockRunStatus.PAUSED,
                allowed_duration_ms=1_000,
                started_at=START,
                paused_at=START - timedelta(milliseconds=1),
            )


class MatchStartPolicyTests(unittest.TestCase):
    participants = ("user-a", "user-b")

    def ready_state(
        self,
        *,
        mode: StartMode = StartMode.BOTH_READY,
        ready_user_ids: frozenset[str] = frozenset(),
        status: ClockRunStatus = ClockRunStatus.READY,
    ) -> MatchStartState:
        return MatchStartState(
            start_mode=mode,
            participant_user_ids=self.participants,
            ready_user_ids=ready_user_ids,
            clock=ClockSnapshot(status=status, allowed_duration_ms=60_000),
        )

    def test_manual_mode_records_readiness_without_auto_start(self) -> None:
        first_ready = mark_player_ready(
            self.ready_state(mode=StartMode.MANUAL), "user-a", START
        )
        both_ready = mark_player_ready(first_ready, "user-b", START)

        self.assertEqual(both_ready.ready_user_ids, frozenset(self.participants))
        self.assertEqual(both_ready.clock.status, ClockRunStatus.READY)
        self.assertIsNone(both_ready.clock.started_at)

    def test_both_ready_starts_at_second_readiness_signal(self) -> None:
        first_ready_at = START + timedelta(seconds=3)
        second_ready_at = START + timedelta(seconds=7)
        first_ready = mark_player_ready(
            self.ready_state(), "user-a", first_ready_at
        )
        retried = mark_player_ready(
            first_ready, "user-a", first_ready_at + timedelta(seconds=1)
        )

        self.assertIs(retried, first_ready)
        self.assertEqual(first_ready.clock.status, ClockRunStatus.READY)
        self.assertIsNone(first_ready.clock.started_at)

        running = mark_player_ready(first_ready, "user-b", second_ready_at)

        self.assertEqual(running.clock.status, ClockRunStatus.RUNNING)
        self.assertEqual(running.clock.started_at, second_ready_at)
        self.assertEqual(running.ready_user_ids, frozenset(self.participants))

    def test_repeated_ready_command_is_idempotent_after_auto_start(self) -> None:
        first_ready = mark_player_ready(self.ready_state(), "user-a", START)
        running = mark_player_ready(
            first_ready, "user-b", START + timedelta(seconds=2)
        )

        self.assertIs(
            mark_player_ready(running, "user-a", START + timedelta(seconds=9)),
            running,
        )

    def test_nonparticipant_cannot_signal_ready(self) -> None:
        with self.assertRaisesRegex(StartPolicyError, "only match participants"):
            mark_player_ready(self.ready_state(), "user-c", START)

    def test_new_ready_signal_requires_ready_run(self) -> None:
        waiting = self.ready_state(status=ClockRunStatus.WAITING)
        running = self.ready_state(status=ClockRunStatus.RUNNING)

        with self.assertRaisesRegex(StartPolicyError, "only for a READY run"):
            mark_player_ready(waiting, "user-a", START)
        with self.assertRaisesRegex(StartPolicyError, "only for a READY run"):
            mark_player_ready(running, "user-a", START)

    def test_ready_gate_rejects_invalid_participants_mode_and_ready_set(self) -> None:
        with self.assertRaisesRegex(StartPolicyError, "exactly two unique"):
            MatchStartState(
                start_mode=StartMode.MANUAL,
                participant_user_ids=("user-a", "user-a"),
                ready_user_ids=frozenset(),
                clock=ready_clock(),
            )
        with self.assertRaisesRegex(StartPolicyError, "unknown match start mode"):
            MatchStartState(
                start_mode="schedule",
                participant_user_ids=self.participants,
                ready_user_ids=frozenset(),
                clock=ready_clock(),
            )
        with self.assertRaisesRegex(StartPolicyError, "only match participants"):
            self.ready_state(ready_user_ids=frozenset(("user-c",)))

    def test_ready_command_requires_aware_start_time(self) -> None:
        with self.assertRaisesRegex(StartPolicyError, "timezone-aware"):
            mark_player_ready(self.ready_state(), "user-a", datetime(2026, 10, 9))


if __name__ == "__main__":
    unittest.main()

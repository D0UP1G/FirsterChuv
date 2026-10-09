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


if __name__ == "__main__":
    unittest.main()

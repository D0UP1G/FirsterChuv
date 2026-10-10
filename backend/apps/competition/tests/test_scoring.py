from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID

from backend.apps.common.contracts import AttemptReceipt, ResultReceipt
from backend.apps.competition.domain.result_ledger import (
    ResultLedger,
    ResultLedgerError,
    apply_result,
    register_accepted,
)

from backend.apps.competition.domain.scoring import (
    FinalTiePolicy,
    ProblemOutcome,
    ScoreInputError,
    ScoreRules,
    ScoredAttempt,
    Verdict,
    calculate_match_score,
)


RUN_ID = "run-1"
PLAYER_A = "user-a"
PLAYER_B = "user-b"
PROBLEM_A = "problem-a"
PROBLEM_B = "problem-b"
START = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)
LEDGER_RUN_ID = UUID(int=100)
LEDGER_OTHER_RUN_ID = UUID(int=101)
LEDGER_USER_A = UUID(int=1)
LEDGER_USER_B = UUID(int=2)
LEDGER_PROBLEM_A = UUID(int=20)


def accepted_receipt(
    submission_id: int,
    elapsed_ms: int,
    *,
    user_id: UUID = LEDGER_USER_A,
    problem_id: UUID = LEDGER_PROBLEM_A,
    run_id: UUID = LEDGER_RUN_ID,
) -> AttemptReceipt:
    return AttemptReceipt(
        submission_id=UUID(int=submission_id),
        run_id=run_id,
        user_id=user_id,
        problem_id=problem_id,
        received_at=START + timedelta(milliseconds=elapsed_ms),
        elapsed_ms=elapsed_ms,
        scoring_version="score-v1",
    )


def final_receipt(accepted: AttemptReceipt, verdict: Verdict) -> ResultReceipt:
    return ResultReceipt(
        submission_id=accepted.submission_id,
        run_id=accepted.run_id,
        user_id=accepted.user_id,
        problem_id=accepted.problem_id,
        received_at=accepted.received_at,
        elapsed_ms=accepted.elapsed_ms,
        scoring_version=accepted.scoring_version,
        verdict=verdict,
    )


def empty_ledger(*, run_id: UUID = LEDGER_RUN_ID) -> ResultLedger:
    return ResultLedger(
        run_id=run_id,
        participant_user_ids=(LEDGER_USER_A, LEDGER_USER_B),
        problem_ids=(LEDGER_PROBLEM_A,),
        scoring_version="score-v1",
        rules=ScoreRules(),
    )


def result(
    submission_id: str,
    user_id: str,
    problem_id: str,
    elapsed_ms: int,
    verdict: Verdict,
    *,
    run_id: str = RUN_ID,
    received_at: datetime | None = None,
) -> ScoredAttempt:
    return ScoredAttempt(
        submission_id=submission_id,
        run_id=run_id,
        user_id=user_id,
        problem_id=problem_id,
        received_at=received_at or START + timedelta(milliseconds=elapsed_ms),
        elapsed_ms=elapsed_ms,
        verdict=verdict,
    )


def score(
    results: list[ScoredAttempt],
    *,
    problem_ids: tuple[str, ...] = (PROBLEM_A,),
    rules: ScoreRules | None = None,
):
    return calculate_match_score(
        run_id=RUN_ID,
        participant_user_ids=(PLAYER_A, PLAYER_B),
        problem_ids=problem_ids,
        results=results,
        rules=rules or ScoreRules(),
    )


class CalculateMatchScoreTests(unittest.TestCase):
    def test_first_ok_and_only_prior_penalized_attempts_affect_score(self) -> None:
        results = [
            result("a-wa-before", PLAYER_A, PROBLEM_A, 10_000, Verdict.WA),
            result("a-ce-before", PLAYER_A, PROBLEM_A, 20_000, Verdict.CE),
            result("a-ok-first", PLAYER_A, PROBLEM_A, 30_000, Verdict.OK),
            result("a-wa-after", PLAYER_A, PROBLEM_A, 40_000, Verdict.WA),
            result("a-ok-repeat", PLAYER_A, PROBLEM_A, 50_000, Verdict.OK),
            result("b-ok", PLAYER_B, PROBLEM_A, 40_000, Verdict.OK),
        ]

        match_score = score(results)

        player_a, player_b = match_score.participants
        task_a = player_a.problems[0]
        self.assertEqual(player_a.solved_count, 1)
        self.assertEqual(player_a.penalty_ms, 90_000)
        self.assertEqual(player_a.last_accepted_elapsed_ms, 30_000)
        self.assertEqual(task_a.outcome, ProblemOutcome.SOLVED)
        self.assertEqual(task_a.attempts, 5)
        self.assertEqual(task_a.last_verdict, Verdict.OK)
        self.assertEqual(task_a.first_ok_elapsed_ms, 30_000)
        self.assertEqual(task_a.penalized_attempts_before_first_ok, 1)
        self.assertEqual(player_b.penalty_ms, 40_000)
        self.assertEqual(match_score.winner_user_id, PLAYER_B)

    def test_solved_count_precedes_penalty_and_time(self) -> None:
        match_score = score(
            [
                result("a1", PLAYER_A, PROBLEM_A, 500_000, Verdict.OK),
                result("a2", PLAYER_A, PROBLEM_B, 500_000, Verdict.OK),
                result("b1", PLAYER_B, PROBLEM_A, 1_000, Verdict.OK),
            ],
            problem_ids=(PROBLEM_A, PROBLEM_B),
        )

        self.assertEqual(match_score.winner_user_id, PLAYER_A)
        self.assertEqual(match_score.participants[0].solved_count, 2)
        self.assertEqual(match_score.participants[1].solved_count, 1)

    def test_penalty_precedes_last_accepted_time(self) -> None:
        match_score = score(
            [
                result("a1", PLAYER_A, PROBLEM_A, 10_000, Verdict.OK),
                result("a2", PLAYER_A, PROBLEM_B, 30_000, Verdict.OK),
                result("b1", PLAYER_B, PROBLEM_A, 10_000, Verdict.OK),
                result("b2-wa", PLAYER_B, PROBLEM_B, 20_000, Verdict.WA),
                result("b2-ok", PLAYER_B, PROBLEM_B, 30_000, Verdict.OK),
            ],
            problem_ids=(PROBLEM_A, PROBLEM_B),
        )

        player_a, player_b = match_score.participants
        self.assertEqual(player_a.last_accepted_elapsed_ms, 30_000)
        self.assertEqual(player_b.last_accepted_elapsed_ms, 30_000)
        self.assertEqual(player_a.penalty_ms, 40_000)
        self.assertEqual(player_b.penalty_ms, 100_000)
        self.assertEqual(match_score.winner_user_id, PLAYER_A)

    def test_last_accepted_time_breaks_a_complete_solved_and_penalty_tie(self) -> None:
        match_score = score(
            [
                result("a1", PLAYER_A, PROBLEM_A, 10_000, Verdict.OK),
                result("a2", PLAYER_A, PROBLEM_B, 30_000, Verdict.OK),
                result("b1", PLAYER_B, PROBLEM_A, 20_000, Verdict.OK),
                result("b2", PLAYER_B, PROBLEM_B, 20_000, Verdict.OK),
            ],
            problem_ids=(PROBLEM_A, PROBLEM_B),
        )

        self.assertEqual(
            [participant.penalty_ms for participant in match_score.participants],
            [40_000, 40_000],
        )
        self.assertEqual(
            [
                participant.last_accepted_elapsed_ms
                for participant in match_score.participants
            ],
            [30_000, 20_000],
        )
        self.assertEqual(match_score.winner_user_id, PLAYER_B)

    def test_equal_score_returns_rematch_required(self) -> None:
        match_score = score(
            [
                result("a1", PLAYER_A, PROBLEM_A, 10_000, Verdict.OK),
                result("b1", PLAYER_B, PROBLEM_A, 10_000, Verdict.OK),
            ]
        )

        self.assertTrue(match_score.tied)
        self.assertTrue(match_score.rematch_required)
        self.assertIsNone(match_score.winner_user_id)

    def test_two_unsolved_players_tie_even_if_only_one_has_attempts(self) -> None:
        match_score = score(
            [result("a-wa", PLAYER_A, PROBLEM_A, 1_000, Verdict.WA)]
        )

        player_a, player_b = match_score.participants
        self.assertEqual(player_a.problems[0].outcome, ProblemOutcome.ATTEMPTED)
        self.assertEqual(player_b.problems[0].outcome, ProblemOutcome.NOT_STARTED)
        self.assertEqual(player_a.penalty_ms, 0)
        self.assertEqual(player_b.penalty_ms, 0)
        self.assertTrue(match_score.tied)
        self.assertTrue(match_score.rematch_required)

    def test_duplicate_identical_result_receipt_is_idempotent(self) -> None:
        accepted = result("same-id", PLAYER_A, PROBLEM_A, 10_000, Verdict.OK)
        match_score = score([accepted, accepted])

        self.assertEqual(match_score.participants[0].problems[0].attempts, 1)
        self.assertEqual(match_score.participants[0].solved_count, 1)

    def test_conflicting_duplicate_submission_id_is_rejected(self) -> None:
        original = result("same-id", PLAYER_A, PROBLEM_A, 10_000, Verdict.WA)
        conflicting = result("same-id", PLAYER_A, PROBLEM_A, 10_000, Verdict.OK)

        with self.assertRaisesRegex(ScoreInputError, "conflicting"):
            score([original, conflicting])

    def test_out_of_order_result_delivery_uses_server_timeline(self) -> None:
        accepted_ok = result("ok", PLAYER_A, PROBLEM_A, 30_000, Verdict.OK)
        earlier_wa = result("wa", PLAYER_A, PROBLEM_A, 10_000, Verdict.WA)

        match_score = score([accepted_ok, earlier_wa])

        player_a = match_score.participants[0]
        self.assertEqual(player_a.problems[0].penalized_attempts_before_first_ok, 1)
        self.assertEqual(player_a.penalty_ms, 90_000)
        self.assertEqual(player_a.problems[0].last_verdict, Verdict.OK)

    def test_non_participant_wrong_run_and_unselected_problem_are_rejected(self) -> None:
        invalid_results = [
            result("foreign-user", "user-c", PROBLEM_A, 1_000, Verdict.OK),
            result("foreign-run", PLAYER_A, PROBLEM_A, 1_000, Verdict.OK, run_id="run-2"),
            result("foreign-problem", PLAYER_A, "problem-c", 1_000, Verdict.OK),
        ]

        for invalid in invalid_results:
            with self.subTest(submission=invalid.submission_id):
                with self.assertRaises(ScoreInputError):
                    score([invalid])

    def test_custom_penalty_set_cannot_penalize_compile_error(self) -> None:
        rules = ScoreRules(
            wrong_attempt_penalty_ms=0,
            penalized_verdicts=(Verdict.WA,),
            final_tie_policy=FinalTiePolicy.REMATCH,
        )

        match_score = score(
            [
                result("ce", PLAYER_A, PROBLEM_A, 1_000, Verdict.CE),
                result("ok", PLAYER_A, PROBLEM_A, 2_000, Verdict.OK),
            ],
            rules=rules,
        )

        self.assertEqual(match_score.participants[0].penalty_ms, 2_000)

    def test_invalid_rule_and_receipt_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ScoreInputError, "non-negative integer"):
            ScoreRules(wrong_attempt_penalty_ms=-1)
        with self.assertRaisesRegex(ScoreInputError, "only WA"):
            ScoreRules(penalized_verdicts=(Verdict.CE,))
        with self.assertRaisesRegex(ScoreInputError, "timezone-aware"):
            ScoredAttempt(
                submission_id="naive",
                run_id=RUN_ID,
                user_id=PLAYER_A,
                problem_id=PROBLEM_A,
                received_at=datetime(2026, 10, 9, 10, 0),
                elapsed_ms=0,
                verdict=Verdict.OK,
            )


class ResultLedgerTests(unittest.TestCase):
    def test_register_accepted_is_immutable_and_idempotent(self) -> None:
        ledger = empty_ledger()
        accepted = accepted_receipt(200, 10_000)

        registered = register_accepted(ledger, accepted)

        self.assertEqual(registered.pending_submission_ids, (accepted.submission_id,))
        self.assertIs(register_accepted(registered, accepted), registered)
        self.assertEqual(ledger.attempts, ())

    def test_conflicting_duplicate_acceptance_is_rejected(self) -> None:
        ledger = register_accepted(empty_ledger(), accepted_receipt(201, 10_000))

        with self.assertRaisesRegex(ResultLedgerError, "different accepted receipt"):
            register_accepted(ledger, accepted_receipt(201, 11_000))

    def test_out_of_order_results_recalculate_from_server_timeline(self) -> None:
        earlier_wa = accepted_receipt(202, 10_000)
        later_ok = accepted_receipt(203, 30_000)
        ledger = register_accepted(empty_ledger(), earlier_wa)
        ledger = register_accepted(ledger, later_ok)

        first_delivery = apply_result(
            ledger,
            final_receipt(later_ok, Verdict.OK),
            current_run_id=LEDGER_RUN_ID,
        )
        self.assertFalse(first_delivery.can_finalize)
        self.assertEqual(first_delivery.ledger.pending_submission_ids, (earlier_wa.submission_id,))
        self.assertEqual(first_delivery.score.participants[0].penalty_ms, 30_000)

        second_delivery = apply_result(
            first_delivery.ledger,
            final_receipt(earlier_wa, Verdict.WA),
            current_run_id=LEDGER_RUN_ID,
        )

        self.assertTrue(second_delivery.can_finalize)
        self.assertTrue(second_delivery.application.applied)
        self.assertEqual(second_delivery.score.participants[0].penalty_ms, 90_000)
        self.assertEqual(
            second_delivery.score.participants[0].problems[0].last_verdict,
            Verdict.OK,
        )

    def test_identical_result_retry_is_idempotent(self) -> None:
        accepted = accepted_receipt(204, 10_000)
        ledger = register_accepted(empty_ledger(), accepted)
        receipt = final_receipt(accepted, Verdict.OK)
        first = apply_result(ledger, receipt, current_run_id=LEDGER_RUN_ID)
        retry = apply_result(first.ledger, receipt, current_run_id=LEDGER_RUN_ID)

        self.assertTrue(first.application.applied)
        self.assertFalse(retry.application.applied)
        self.assertIs(retry.ledger, first.ledger)
        self.assertEqual(retry.score, first.score)

    def test_conflicting_duplicate_result_is_rejected(self) -> None:
        accepted = accepted_receipt(205, 10_000)
        ledger = register_accepted(empty_ledger(), accepted)
        ledger = apply_result(
            ledger,
            final_receipt(accepted, Verdict.WA),
            current_run_id=LEDGER_RUN_ID,
        ).ledger

        with self.assertRaisesRegex(ResultLedgerError, "conflicting result"):
            apply_result(
                ledger,
                final_receipt(accepted, Verdict.OK),
                current_run_id=LEDGER_RUN_ID,
            )

    def test_result_must_match_the_immutable_accepted_timing(self) -> None:
        accepted = accepted_receipt(206, 10_000)
        ledger = register_accepted(empty_ledger(), accepted)
        forged = ResultReceipt(
            submission_id=accepted.submission_id,
            run_id=accepted.run_id,
            user_id=accepted.user_id,
            problem_id=accepted.problem_id,
            received_at=accepted.received_at + timedelta(milliseconds=1),
            elapsed_ms=accepted.elapsed_ms,
            scoring_version=accepted.scoring_version,
            verdict=Verdict.OK,
        )

        with self.assertRaisesRegex(ResultLedgerError, "differs from accepted"):
            apply_result(ledger, forged, current_run_id=LEDGER_RUN_ID)

    def test_unknown_result_cannot_create_an_accepted_attempt(self) -> None:
        accepted = accepted_receipt(207, 10_000)

        with self.assertRaisesRegex(ResultLedgerError, "no accepted ledger"):
            apply_result(
                empty_ledger(),
                final_receipt(accepted, Verdict.OK),
                current_run_id=LEDGER_RUN_ID,
            )

    def test_superseded_run_result_is_recorded_but_not_scored(self) -> None:
        accepted = accepted_receipt(208, 10_000)
        ledger = register_accepted(empty_ledger(), accepted)

        stale = apply_result(
            ledger,
            final_receipt(accepted, Verdict.OK),
            current_run_id=LEDGER_OTHER_RUN_ID,
        )

        self.assertFalse(stale.application.applied)
        self.assertIsNone(stale.score)
        self.assertFalse(stale.can_finalize)
        self.assertEqual(stale.ledger.pending_submission_ids, ())

    def test_acceptance_receipt_must_match_run_snapshot(self) -> None:
        with self.assertRaisesRegex(ResultLedgerError, "another run"):
            register_accepted(
                empty_ledger(),
                accepted_receipt(209, 10_000, run_id=LEDGER_OTHER_RUN_ID),
            )


if __name__ == "__main__":
    unittest.main()

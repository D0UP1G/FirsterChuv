from datetime import datetime, timedelta, timezone
import unittest

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


if __name__ == "__main__":
    unittest.main()

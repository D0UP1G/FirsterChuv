"""Allowlisted private MatchView projection for the current persisted run."""

from datetime import datetime

from django.db.models import Max

from backend.apps.competition.domain.clock import (
    ClockError,
    ClockSnapshot,
    active_elapsed_ms,
)
from backend.apps.competition.domain.scoring import (
    FinalTiePolicy,
    ScoredAttempt,
    ScoreInputError,
    ScoreRules,
    Verdict,
    calculate_match_score,
)
from backend.apps.competition.models import Match, MatchRun, MatchRunReady, MatchSlot
from backend.apps.events.models import MatchEvent
from backend.apps.submissions.models import Submission


class MatchProjectionError(ValueError):
    """Persisted match data cannot be represented by the v1 private DTO."""

    def __init__(self, message: str, *, code: str = "match_state_unavailable"):
        self.code = code
        super().__init__(message)


def _elapsed_ms(run: MatchRun, now: datetime) -> int:
    if run.started_at is None:
        return 0
    if run.status in (MatchRun.Status.RUNNING, MatchRun.Status.PAUSED):
        try:
            return active_elapsed_ms(
                ClockSnapshot(
                    status=run.status,
                    allowed_duration_ms=run.allowed_duration_ms,
                    started_at=run.started_at,
                    paused_at=run.paused_at,
                    accumulated_pause_ms=run.accumulated_pause_ms,
                ),
                now,
            )
        except ClockError as error:
            raise MatchProjectionError("Снимок часов матча повреждён.") from error

    endpoint = run.finished_at or now
    wall_ms = int((endpoint - run.started_at).total_seconds() * 1000)
    return min(
        run.allowed_duration_ms,
        max(0, wall_ms - run.accumulated_pause_ms),
    )


def _score_rules(snapshot: dict) -> ScoreRules:
    try:
        return ScoreRules(
            wrong_attempt_penalty_ms=snapshot["wrongAttemptPenaltySec"] * 1000,
            penalized_verdicts=tuple(
                Verdict(item) for item in snapshot["penalizedVerdicts"]
            ),
            final_tie_policy=FinalTiePolicy(snapshot["finalTiePolicy"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise MatchProjectionError("Снимок правил матча повреждён.") from error


def match_view_payload(match: Match, *, actor, now: datetime) -> dict:
    """Build the v1 MatchView without selecting source or diagnostics columns."""
    run = match.current_run
    if run is None:
        raise MatchProjectionError(
            "У матча ещё нет настроенного запуска.",
            code="match_run_not_configured",
        )

    slots = list(
        MatchSlot.objects.filter(
            match_id=match.pk,
            resolution=MatchSlot.Resolution.PLAYER,
        )
        .select_related("participant__user")
        .order_by("slot_index")
    )
    if len(slots) != 2 or len({slot.participant.user_id for slot in slots}) != 2:
        raise MatchProjectionError("В текущем запуске должны быть два разных участника.")

    user_ids = tuple(str(slot.participant.user_id) for slot in slots)
    problems = tuple(run.problem_versions)
    problem_ids = tuple(str(item["problemId"]) for item in problems)
    if not problem_ids or len(set(problem_ids)) != len(problem_ids):
        raise MatchProjectionError("Снимок задач запуска повреждён.")

    # Source and compile diagnostics remain deferred and never enter this read DTO.
    submissions = list(
        Submission.objects.filter(run_id=run.pk)
        .only(
            "id",
            "actor_id",
            "problem_id",
            "received_at",
            "elapsed_ms",
            "status",
            "verdict",
        )
        .order_by("received_at", "id")
    )
    allowed_users = set(user_ids)
    allowed_problems = set(problem_ids)
    if any(
        str(item.actor_id) not in allowed_users
        or str(item.problem_id) not in allowed_problems
        for item in submissions
    ):
        raise MatchProjectionError(
            "Состав запуска не совпадает с текущими слотами матча."
        )

    scored_attempts = [
        ScoredAttempt(
            submission_id=str(item.pk),
            run_id=str(run.pk),
            user_id=str(item.actor_id),
            problem_id=str(item.problem_id),
            received_at=item.received_at,
            elapsed_ms=item.elapsed_ms,
            verdict=Verdict(item.verdict),
        )
        for item in submissions
        if item.status == Submission.Status.FINISHED and item.verdict is not None
    ]
    try:
        score = calculate_match_score(
            run_id=str(run.pk),
            participant_user_ids=user_ids,
            problem_ids=problem_ids,
            results=scored_attempts,
            rules=_score_rules(run.score_rule),
        )
    except ScoreInputError as error:
        raise MatchProjectionError("Снимок результатов матча повреждён.") from error
    score_by_user = {item.user_id: item for item in score.participants}
    submissions_by_pair: dict[tuple[str, str], list[Submission]] = {}
    for item in submissions:
        submissions_by_pair.setdefault(
            (str(item.actor_id), str(item.problem_id)), []
        ).append(item)

    players = []
    for slot in slots:
        participant = slot.participant
        user_id = str(participant.user_id)
        participant_score = score_by_user[user_id]
        problems_by_id = {
            item.problem_id: item for item in participant_score.problems
        }
        task_states = []
        for problem in problems:
            problem_id = str(problem["problemId"])
            attempts = submissions_by_pair.get((user_id, problem_id), [])
            problem_score = problems_by_id[problem_id]
            outcome = problem_score.outcome.value
            if outcome == "NOT_STARTED" and attempts:
                outcome = "ATTEMPTED"
            latest = attempts[-1] if attempts else None
            task_states.append(
                {
                    "problemId": problem_id,
                    "label": problem["label"],
                    "status": outcome,
                    "attempts": len(attempts),
                    "lastVerdict": latest.verdict if latest else None,
                }
            )
        players.append(
            {
                "userId": user_id,
                "displayName": participant.user.display_name,
                "solvedCount": participant_score.solved_count,
                "penaltyMs": participant_score.penalty_ms,
                "lastAcceptedElapsedMs": participant_score.last_accepted_elapsed_ms,
                "tasks": task_states,
            }
        )

    elapsed_ms = _elapsed_ms(run, now)
    ready_user_ids = sorted(
        str(user_id)
        for user_id in MatchRunReady.objects.filter(run=run).values_list(
            "participant__user_id", flat=True
        )
    )
    last_event_id = (
        MatchEvent.objects.filter(match_id=match.pk, run_id=run.pk).aggregate(
            latest=Max("id")
        )["latest"]
        or 0
    )
    is_admin = getattr(actor, "role", None) == "admin"
    condition_available = is_admin or run.started_at is not None
    return {
        "matchId": str(match.pk),
        "runId": str(run.pk),
        "status": run.status,
        "serverNow": now.isoformat().replace("+00:00", "Z"),
        "elapsedMs": elapsed_ms,
        "remainingMs": max(0, run.allowed_duration_ms - elapsed_ms),
        "allowedDurationMs": run.allowed_duration_ms,
        "leaderUserId": score.winner_user_id,
        "winnerUserId": match.winner.user_id if match.winner_id else None,
        "lastEventId": last_event_id,
        "scoringRule": run.score_rule,
        "players": players,
        "tournamentId": str(match.tournament_id),
        "startMode": run.start_mode,
        "readyUserIds": ready_user_ids,
        "problemVersions": [
            {
                "problemId": str(item["problemId"]),
                "label": item["label"],
                "version": item["version"],
                "conditionAvailable": condition_available,
            }
            for item in problems
        ],
    }

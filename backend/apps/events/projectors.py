"""Typed projections from internal match results to public event payloads."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from backend.apps.competition.domain.scoring import (
    MatchScore,
    ParticipantScore,
    ProblemScore,
)
from backend.apps.events.public_payloads import (
    PublicEventInputError,
    validate_score_changed_payload,
)


def _canonical_uuid(value: object, *, name: str) -> str:
    if not isinstance(value, (str, UUID)):
        raise PublicEventInputError(f"{name} must be a UUID")
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError) as error:
        raise PublicEventInputError(f"{name} must be a UUID") from error


def _canonical_mapping_keys(
    values: Mapping[object, object], *, name: str
) -> dict[str, object]:
    if not isinstance(values, Mapping):
        raise PublicEventInputError(f"{name} must be a mapping")
    result: dict[str, object] = {}
    for raw_key, value in values.items():
        key = _canonical_uuid(raw_key, name=f"{name} key")
        if key in result:
            raise PublicEventInputError(f"{name} keys must be unique UUIDs")
        result[key] = value
    return result


def project_score_changed_payload(
    score: MatchScore,
    *,
    display_names: Mapping[str | UUID, str],
    problem_labels: Mapping[str | UUID, str],
) -> dict:
    """Project one score into the allowlisted public ``score.changed`` DTO.

    Public names and task labels must be supplied by the caller from its
    authorized display metadata. Private source, email, judge diagnostics, and
    other internal fields are never accepted as inputs to this projector.
    """
    if not isinstance(score, MatchScore):
        raise PublicEventInputError("score must be a MatchScore")
    if len(score.participants) != 2 or any(
        not isinstance(participant, ParticipantScore)
        for participant in score.participants
    ):
        raise PublicEventInputError("score must contain exactly two participants")

    user_ids = tuple(
        _canonical_uuid(participant.user_id, name="participant user ID")
        for participant in score.participants
    )
    if len(set(user_ids)) != 2:
        raise PublicEventInputError("participant user IDs must be unique")

    projected_names = _canonical_mapping_keys(display_names, name="display_names")
    if set(projected_names) != set(user_ids):
        raise PublicEventInputError("display_names must map exactly the match players")

    per_player_problem_ids: list[tuple[str, ...]] = []
    for participant in score.participants:
        if any(not isinstance(problem, ProblemScore) for problem in participant.problems):
            raise PublicEventInputError("participant problems must be ProblemScore values")
        problem_ids = tuple(
            _canonical_uuid(problem.problem_id, name="problem ID")
            for problem in participant.problems
        )
        if not problem_ids or len(set(problem_ids)) != len(problem_ids):
            raise PublicEventInputError("each player must have unique scored problems")
        per_player_problem_ids.append(problem_ids)

    if per_player_problem_ids[0] != per_player_problem_ids[1]:
        raise PublicEventInputError("both players must have the same ordered problem list")

    problem_ids = per_player_problem_ids[0]
    projected_labels = _canonical_mapping_keys(problem_labels, name="problem_labels")
    if set(projected_labels) != set(problem_ids):
        raise PublicEventInputError("problem_labels must map exactly the scored problems")

    players = []
    for participant, user_id in zip(score.participants, user_ids, strict=True):
        tasks = []
        for problem, problem_id in zip(
            participant.problems, problem_ids, strict=True
        ):
            outcome = getattr(problem.outcome, "value", problem.outcome)
            verdict = (
                getattr(problem.last_verdict, "value", problem.last_verdict)
                if problem.last_verdict is not None
                else None
            )
            tasks.append(
                {
                    "problemId": problem_id,
                    "label": projected_labels[problem_id],
                    "status": outcome,
                    "attempts": problem.attempts,
                    "lastVerdict": verdict,
                }
            )
        players.append(
            {
                "userId": user_id,
                "displayName": projected_names[user_id],
                "solvedCount": participant.solved_count,
                "penaltyMs": participant.penalty_ms,
                "lastAcceptedElapsedMs": participant.last_accepted_elapsed_ms,
                "tasks": tasks,
            }
        )

    winner_user_id = (
        _canonical_uuid(score.winner_user_id, name="winner user ID")
        if score.winner_user_id is not None
        else None
    )
    return validate_score_changed_payload(
        {"leaderUserId": winner_user_id, "players": players}
    )

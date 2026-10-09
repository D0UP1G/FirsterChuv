"""Strict allowlist for public event payloads supported by this slice."""

from __future__ import annotations

from uuid import UUID


class PublicEventInputError(ValueError):
    """Raised when an event payload does not match its public contract."""


VERDICTS = frozenset(("OK", "WA", "TL", "ML", "RE", "CE"))
TASK_STATUSES = frozenset(("NOT_STARTED", "ATTEMPTED", "SOLVED"))


def _object(value: object, *, keys: frozenset[str], name: str) -> dict:
    if not isinstance(value, dict):
        raise PublicEventInputError(f"{name} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise PublicEventInputError(f"{name} keys must be strings")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise PublicEventInputError(
            f"{name} keys mismatch (missing={missing}, extra={extra})"
        )
    return value


def _uuid_text(value: object, *, name: str) -> str:
    if not isinstance(value, (str, UUID)):
        raise PublicEventInputError(f"{name} must be a UUID")
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError) as error:
        raise PublicEventInputError(f"{name} must be a UUID") from error


def _count(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise PublicEventInputError(f"{name} must be a non-negative integer")
    return value


def _text(value: object, *, name: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise PublicEventInputError(f"{name} must be a non-empty string up to {max_length} characters")
    return value


def validate_score_changed_payload(payload: object) -> dict:
    """Validate and copy the fixture-backed score.changed public payload.

    Unknown keys fail closed at every object level. User-facing text remains
    plain JSON data; consumers must render it as text rather than HTML.
    """
    top = _object(
        payload,
        keys=frozenset(("leaderUserId", "players")),
        name="score.changed payload",
    )
    if not isinstance(top["players"], list) or len(top["players"]) != 2:
        raise PublicEventInputError("score.changed players must contain exactly two players")

    players: list[dict] = []
    seen_users: set[str] = set()
    canonical_tasks: tuple[tuple[str, str], ...] | None = None
    for index, raw_player in enumerate(top["players"]):
        player_name = f"players[{index}]"
        player = _object(
            raw_player,
            keys=frozenset(
                (
                    "userId",
                    "displayName",
                    "solvedCount",
                    "penaltyMs",
                    "lastAcceptedElapsedMs",
                    "tasks",
                )
            ),
            name=player_name,
        )
        user_id = _uuid_text(player["userId"], name=f"{player_name}.userId")
        if user_id in seen_users:
            raise PublicEventInputError("score.changed player user IDs must be unique")
        seen_users.add(user_id)

        display_name = _text(
            player["displayName"], name=f"{player_name}.displayName", max_length=80
        )
        solved_count = _count(player["solvedCount"], name=f"{player_name}.solvedCount")
        penalty_ms = _count(player["penaltyMs"], name=f"{player_name}.penaltyMs")
        last_accepted = player["lastAcceptedElapsedMs"]
        if last_accepted is not None:
            last_accepted = _count(
                last_accepted, name=f"{player_name}.lastAcceptedElapsedMs"
            )
        if not isinstance(player["tasks"], list) or not player["tasks"]:
            raise PublicEventInputError(f"{player_name}.tasks must be a non-empty array")

        tasks: list[dict] = []
        seen_problems: set[str] = set()
        seen_labels: set[str] = set()
        solved_tasks = 0
        for task_index, raw_task in enumerate(player["tasks"]):
            task_name = f"{player_name}.tasks[{task_index}]"
            task = _object(
                raw_task,
                keys=frozenset(("problemId", "label", "status", "attempts", "lastVerdict")),
                name=task_name,
            )
            problem_id = _uuid_text(task["problemId"], name=f"{task_name}.problemId")
            label = _text(task["label"], name=f"{task_name}.label", max_length=40)
            status = task["status"]
            attempts = _count(task["attempts"], name=f"{task_name}.attempts")
            verdict = task["lastVerdict"]
            if not isinstance(status, str) or status not in TASK_STATUSES:
                raise PublicEventInputError(f"{task_name}.status is not public")
            if verdict is not None and (
                not isinstance(verdict, str) or verdict not in VERDICTS
            ):
                raise PublicEventInputError(f"{task_name}.lastVerdict is not normalized")
            if problem_id in seen_problems or label in seen_labels:
                raise PublicEventInputError("task problem IDs and labels must be unique per player")
            seen_problems.add(problem_id)
            seen_labels.add(label)

            if status == "NOT_STARTED" and (attempts != 0 or verdict is not None):
                raise PublicEventInputError("NOT_STARTED tasks must have no attempts or verdict")
            if status == "ATTEMPTED" and (
                attempts == 0 or verdict is None or verdict == "OK"
            ):
                raise PublicEventInputError("ATTEMPTED tasks require a non-OK verdict")
            if status == "SOLVED":
                if attempts == 0 or verdict is None:
                    raise PublicEventInputError(
                        "SOLVED tasks require an attempt verdict"
                    )
                solved_tasks += 1

            tasks.append(
                {
                    "problemId": problem_id,
                    "label": label,
                    "status": status,
                    "attempts": attempts,
                    "lastVerdict": verdict,
                }
            )

        task_signature = tuple((task["problemId"], task["label"]) for task in tasks)
        if canonical_tasks is None:
            canonical_tasks = task_signature
        elif task_signature != canonical_tasks:
            raise PublicEventInputError("both players must have the same ordered task list")
        if solved_count != solved_tasks:
            raise PublicEventInputError("solvedCount must match SOLVED task states")
        if (solved_count == 0) != (last_accepted is None):
            raise PublicEventInputError("lastAcceptedElapsedMs must match solvedCount")

        players.append(
            {
                "userId": user_id,
                "displayName": display_name,
                "solvedCount": solved_count,
                "penaltyMs": penalty_ms,
                "lastAcceptedElapsedMs": last_accepted,
                "tasks": tasks,
            }
        )

    leader_user_id = top["leaderUserId"]
    if leader_user_id is not None:
        leader_user_id = _uuid_text(leader_user_id, name="leaderUserId")
        if leader_user_id not in seen_users:
            raise PublicEventInputError("leaderUserId must be one of the match players")

    return {"leaderUserId": leader_user_id, "players": players}

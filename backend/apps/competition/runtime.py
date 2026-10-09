"""Persisted configuration and readiness/start transitions for match runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from django.db import models, transaction

from backend.apps.common.contracts import ProblemCatalogV1
from backend.apps.competition.domain.clock import (
    ClockRunStatus,
    ClockSnapshot,
    start_clock,
)
from backend.apps.competition.domain.scoring import (
    FinalTiePolicy,
    ScoreRules,
    Verdict,
)
from backend.apps.competition.domain.start_policy import (
    MatchStartState,
    StartMode,
    StartPolicyError,
    mark_player_ready,
)
from backend.apps.competition.models import Match, MatchRun, MatchRunReady, MatchSlot
from backend.apps.problems.errors import ProblemNotReady
from backend.apps.tournaments.models import TournamentParticipant


class MatchRuntimeError(RuntimeError):
    """A requested persisted match-run transition cannot be applied."""

    status_code = 409
    code = "match_runtime_conflict"


def _score_rule(value: Mapping[str, object] | None) -> tuple[ScoreRules, dict]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise MatchRuntimeError("scoringRule must be an object")
    allowed = {"order", "wrongAttemptPenaltySec", "penalizedVerdicts", "finalTiePolicy"}
    if set(value) - allowed:
        raise MatchRuntimeError("scoringRule contains unsupported fields")
    order = value.get("order", ["solved_desc", "penalty_asc", "last_accepted_asc"])
    if order != ["solved_desc", "penalty_asc", "last_accepted_asc"]:
        raise MatchRuntimeError("scoring order is fixed by the match contract")
    penalty_sec = value.get("wrongAttemptPenaltySec", 60)
    if type(penalty_sec) is not int or penalty_sec < 0:
        raise MatchRuntimeError("wrongAttemptPenaltySec must be a non-negative integer")
    verdicts = value.get("penalizedVerdicts", ["WA", "TL", "ML", "RE"])
    try:
        rules = ScoreRules(
            wrong_attempt_penalty_ms=penalty_sec * 1000,
            penalized_verdicts=tuple(Verdict(item) for item in verdicts),
            final_tie_policy=FinalTiePolicy(value.get("finalTiePolicy", "rematch")),
        )
    except (TypeError, ValueError) as error:
        raise MatchRuntimeError("scoringRule is invalid") from error
    snapshot = {
        "order": list(order),
        "wrongAttemptPenaltySec": rules.wrong_attempt_penalty_ms // 1000,
        "penalizedVerdicts": [item.value for item in rules.penalized_verdicts],
        "finalTiePolicy": rules.final_tie_policy.value,
    }
    return rules, snapshot


def _problem_snapshot(problem_ids: Sequence[UUID | str], catalog: ProblemCatalogV1) -> list[dict]:
    try:
        normalized_ids = tuple(UUID(str(item)) for item in problem_ids)
    except (TypeError, ValueError, AttributeError) as error:
        raise MatchRuntimeError("problemIds must contain UUIDs") from error
    if not normalized_ids or len(set(normalized_ids)) != len(normalized_ids):
        raise MatchRuntimeError("problemIds must be a non-empty unique sequence")
    try:
        described = catalog.describe_ready(normalized_ids)
        if tuple(item.problem_id for item in described) != normalized_ids:
            raise ProblemNotReady("catalog did not return the requested ready versions")
        result = []
        for item in described:
            bundle = catalog.load_bundle(item.problem_id, item.version)
            if bundle.problem_id != item.problem_id or bundle.version != item.version:
                raise ProblemNotReady("catalog bundle does not match its ready summary")
            result.append({
                "problemId": str(item.problem_id),
                "label": item.label,
                "version": item.version,
                "checksum": bundle.checksum,
                "conditionAvailable": True,
                "timeLimitMs": item.time_limit_ms,
                "memoryLimitBytes": item.memory_limit_bytes,
                "languageIds": [language.id for language in item.languages],
            })
        return result
    except Exception as error:
        if isinstance(error, MatchRuntimeError):
            raise
        raise MatchRuntimeError("a configured problem is not ready for execution") from error


@transaction.atomic
def configure_match_run(
    match_id: UUID | str,
    *,
    problem_ids: Sequence[UUID | str],
    allowed_duration_ms: int,
    start_mode: StartMode | str,
    scoring_rule: Mapping[str, object] | None,
    catalog: ProblemCatalogV1,
) -> MatchRun:
    """Create the first run from verified immutable task and rule snapshots."""
    if type(allowed_duration_ms) is not int or allowed_duration_ms < 1:
        raise MatchRuntimeError("allowedDurationMs must be a positive integer")
    try:
        normalized_mode = StartMode(start_mode)
    except ValueError as error:
        raise MatchRuntimeError("startMode is invalid") from error
    _rules, rules_snapshot = _score_rule(scoring_rule)
    problems = _problem_snapshot(problem_ids, catalog)

    changed = Match.objects.filter(pk=match_id, kind=Match.Kind.PLAYED).update(
        updated_at=models.F("updated_at")
    )
    if not changed:
        raise MatchRuntimeError("played match was not found")
    match = Match.objects.select_related("current_run").get(pk=match_id)
    slots = list(
        MatchSlot.objects.filter(match=match, resolution=MatchSlot.Resolution.PLAYER)
        .select_related("participant")
        .order_by("slot_index")
    )
    if len(slots) != 2 or len({slot.participant_id for slot in slots}) != 2:
        raise MatchRuntimeError("both match participants must be assigned")
    if match.current_run_id:
        current = match.current_run
        if (
            current.status == MatchRun.Status.READY
            and current.allowed_duration_ms == allowed_duration_ms
            and current.start_mode == normalized_mode
            and current.score_rule == rules_snapshot
            and current.problem_versions == problems
        ):
            return current
        raise MatchRuntimeError("match already has a configured run")
    if match.status != Match.Status.WAITING:
        raise MatchRuntimeError("only a waiting match can be configured")

    sequence = (match.runs.aggregate(latest=models.Max("sequence"))["latest"] or 0) + 1
    run = MatchRun.objects.create(
        match=match,
        sequence=sequence,
        status=MatchRun.Status.READY,
        allowed_duration_ms=allowed_duration_ms,
        score_rule=rules_snapshot,
        start_mode=normalized_mode,
        problem_versions=problems,
    )
    match.current_run = run
    match.status = Match.Status.READY
    match.save(update_fields=("current_run", "status", "updated_at"))
    return run


def _claim_run(run_id: UUID | str) -> MatchRun:
    """Acquire a SQLite write reservation before reading state to mutate."""
    changed = MatchRun.objects.filter(
        pk=run_id,
        match__current_run_id=run_id,
        status__in=(MatchRun.Status.READY, MatchRun.Status.RUNNING),
    ).update(revision=models.F("revision"))
    if not changed:
        raise MatchRuntimeError("current match run is not ready for this command")
    return MatchRun.objects.select_related("match").get(pk=run_id)


def _persist_transition(run: MatchRun, *, status: str, started_at: datetime | None) -> MatchRun:
    changed = MatchRun.objects.filter(pk=run.pk, revision=run.revision).update(
        status=status,
        started_at=started_at,
        revision=models.F("revision") + 1,
    )
    if not changed:
        raise MatchRuntimeError("match run changed concurrently")
    Match.objects.filter(pk=run.match_id, current_run_id=run.pk).update(
        status=status,
        updated_at=models.functions.Now(),
    )
    run.refresh_from_db()
    return run


@transaction.atomic
def mark_match_ready(run_id: UUID | str, *, actor_user_id: UUID | str, now: datetime) -> MatchRun:
    """Persist readiness and auto-start only when the selected policy permits."""
    run = _claim_run(run_id)
    if run.status == MatchRun.Status.RUNNING:
        ready = MatchRunReady.objects.filter(run=run, participant__user_id=actor_user_id).exists()
        if ready:
            return run
        raise MatchRuntimeError("a running match cannot accept a new readiness signal")
    slots = list(
        MatchSlot.objects.filter(match=run.match, resolution=MatchSlot.Resolution.PLAYER)
        .select_related("participant")
        .order_by("slot_index")
    )
    participant_by_user = {str(slot.participant.user_id): slot.participant for slot in slots}
    actor_key = str(actor_user_id)
    if actor_key not in participant_by_user or len(participant_by_user) != 2:
        raise MatchRuntimeError("only the two current match participants can become ready")
    ready_rows = list(MatchRunReady.objects.filter(run=run).select_related("participant"))
    ready_ids = frozenset(str(row.participant.user_id) for row in ready_rows)
    state = MatchStartState(
        start_mode=run.start_mode,
        participant_user_ids=tuple(participant_by_user),
        ready_user_ids=ready_ids,
        clock=ClockSnapshot(
            status=run.status,
            allowed_duration_ms=run.allowed_duration_ms,
            started_at=run.started_at,
            paused_at=run.paused_at,
            accumulated_pause_ms=run.accumulated_pause_ms,
        ),
    )
    try:
        updated = mark_player_ready(state, actor_key, now)
    except StartPolicyError as error:
        raise MatchRuntimeError(str(error)) from error
    if actor_key not in ready_ids:
        MatchRunReady.objects.create(run=run, participant=participant_by_user[actor_key])
    if updated.clock.status is ClockRunStatus.RUNNING:
        return _persist_transition(run, status=MatchRun.Status.RUNNING, started_at=updated.clock.started_at)
    if actor_key not in ready_ids:
        run.revision += 1
        run.save(update_fields=("revision",))
    return run


@transaction.atomic
def start_match_run(run_id: UUID | str, *, now: datetime) -> MatchRun:
    """Start a manually configured current run using server time."""
    run = _claim_run(run_id)
    if run.start_mode != MatchRun.StartMode.MANUAL:
        raise MatchRuntimeError("manual start is disabled for this match")
    if run.status == MatchRun.Status.RUNNING:
        return run
    try:
        clock = start_clock(
            ClockSnapshot(
                status=run.status,
                allowed_duration_ms=run.allowed_duration_ms,
                started_at=run.started_at,
                paused_at=run.paused_at,
                accumulated_pause_ms=run.accumulated_pause_ms,
            ),
            now,
        )
    except ValueError as error:
        raise MatchRuntimeError(str(error)) from error
    return _persist_transition(run, status=clock.status.value, started_at=clock.started_at)

"""Production competition ports over the persisted match/run snapshots."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from backend.apps.accounts.models import User
from backend.apps.common.contracts import (
    AttemptReceipt,
    CompetitionGatewayV1,
    InfrastructureFailureReceipt,
    ResultApplication,
    ResultReceipt,
    RunProblemSnapshot,
    RunProblemSnapshotProvider,
    SubmissionPermit,
    WorkspaceAction,
    WorkspaceContext,
    WorkspacePurpose,
)
from backend.apps.competition.domain.clock import ClockError, ClockSnapshot, submission_elapsed_ms
from backend.apps.competition.ledger_persistence import (
    apply_result as persist_result,
    record_infrastructure_failure as persist_infrastructure_failure,
    register_accepted as persist_accepted,
)
from backend.apps.competition.models import Match, MatchRun
from backend.apps.tournaments.models import TournamentParticipant


_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_WORKSPACE_ACTIONS: dict[WorkspacePurpose, frozenset[WorkspaceAction]] = {
    "metadata": frozenset({"read_metadata"}),
    "statement": frozenset({"read_statement"}),
    "draft": frozenset({"read_draft", "write_draft"}),
    "history": frozenset({"read_history"}),
}


class CompetitionGatewayConflict(APIException):
    """The requested operation conflicts with this run's persisted state."""

    status_code = 409
    default_code = "competition_run_conflict"
    default_detail = "Действие недоступно для текущего состояния матча."


class CompetitionGatewayUnavailable(APIException):
    """The persisted access snapshot is internally inconsistent."""

    status_code = 503
    default_code = "competition_snapshot_unavailable"
    default_detail = "Снимок запуска матча временно недоступен."


class CompetitionSnapshotUnavailable(RuntimeError):
    """A trusted runtime snapshot is missing or internally inconsistent."""

    code = "competition_snapshot_unavailable"


class RunProblemSnapshotUnavailable(CompetitionSnapshotUnavailable):
    """The immutable task assignment is missing or internally inconsistent."""


def _not_found() -> NotFound:
    # Keep private match, actor, and task identifiers indistinguishable.
    return NotFound("Рабочая область не найдена.", code="workspace_not_found")


def _normalized_uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _run_problem_entry(run: MatchRun, problem_id: UUID) -> dict[str, object]:
    """Validate the run-owned assignment without consulting the latest catalog."""
    assignments = run.problem_versions
    if not isinstance(assignments, list) or not assignments:
        raise RunProblemSnapshotUnavailable()

    normalized: list[tuple[UUID, dict[str, object]]] = []
    for entry in assignments:
        if not isinstance(entry, dict):
            raise RunProblemSnapshotUnavailable()
        assigned_id = _normalized_uuid(entry.get("problemId"))
        version = entry.get("version")
        checksum = entry.get("checksum")
        if (
            assigned_id is None
            or not isinstance(version, str)
            or not version
            or len(version) > 64
            or not isinstance(checksum, str)
            or not _SHA256_RE.fullmatch(checksum)
        ):
            raise RunProblemSnapshotUnavailable()
        normalized.append((assigned_id, entry))

    assigned_ids = [item[0] for item in normalized]
    if len(set(assigned_ids)) != len(assigned_ids):
        raise RunProblemSnapshotUnavailable()
    selected = [entry for assigned_id, entry in normalized if assigned_id == problem_id]
    if len(selected) != 1:
        raise _not_found()
    return selected[0]


def _frozen_participant_ids(run: MatchRun) -> tuple[UUID, UUID]:
    values = run.participant_user_ids
    if not isinstance(values, list) or len(values) != 2:
        raise CompetitionSnapshotUnavailable()
    participants = tuple(_normalized_uuid(value) for value in values)
    if any(value is None for value in participants) or len(set(participants)) != 2:
        raise CompetitionSnapshotUnavailable()
    return participants  # type: ignore[return-value]


def _clock_snapshot(run: MatchRun) -> ClockSnapshot:
    return ClockSnapshot(
        status=run.status,
        allowed_duration_ms=run.allowed_duration_ms,
        started_at=run.started_at,
        paused_at=run.paused_at,
        accumulated_pause_ms=run.accumulated_pause_ms,
    )


class DjangoCompetitionGateway(CompetitionGatewayV1, RunProblemSnapshotProvider):
    """CompetitionGatewayV1 and immutable task-snapshot provider for A3 ports."""

    def resolve(self, run_id: UUID, problem_id: UUID) -> RunProblemSnapshot:
        run = MatchRun.objects.filter(pk=run_id).first()
        if run is None:
            raise _not_found()
        entry = _run_problem_entry(run, problem_id)
        return RunProblemSnapshot(
            run_id=run.pk,
            problem_id=problem_id,
            problem_version=str(entry["version"]),
            problem_checksum=str(entry["checksum"]),
        )

    def authorize_submission(
        self,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        received_at: datetime,
    ) -> SubmissionPermit:
        if not isinstance(received_at, datetime) or not timezone.is_aware(received_at):
            raise CompetitionGatewayConflict("Время приёма должно быть задано сервером.")

        match = (
            Match.objects.filter(pk=match_id, kind=Match.Kind.PLAYED)
            .select_related("current_run")
            .first()
        )
        run = MatchRun.objects.filter(pk=run_id, match_id=match_id).first()
        if match is None or run is None:
            raise _not_found()
        if match.current_run_id != run.pk:
            raise CompetitionGatewayConflict("Указанный запуск уже не является текущим.")

        try:
            participants = _frozen_participant_ids(run)
            _run_problem_entry(run, problem_id)
        except CompetitionSnapshotUnavailable as error:
            raise CompetitionGatewayUnavailable() from error
        if actor_id not in participants:
            raise _not_found()
        if not TournamentParticipant.objects.filter(
            tournament_id=match.tournament_id,
            user_id=actor_id,
            status=TournamentParticipant.Status.ACTIVE,
            user__is_active=True,
            user__role=User.Roles.PARTICIPANT,
        ).exists():
            raise _not_found()

        if run.status != MatchRun.Status.RUNNING:
            raise CompetitionGatewayConflict()
        try:
            elapsed_ms = submission_elapsed_ms(_clock_snapshot(run), received_at)
        except ClockError as error:
            raise CompetitionGatewayConflict() from error
        if not isinstance(run.scoring_version, str) or not run.scoring_version:
            raise RunProblemSnapshotUnavailable()
        return SubmissionPermit(
            run_id=run.pk,
            elapsed_ms=elapsed_ms,
            scoring_version=run.scoring_version,
        )

    def register_accepted(self, receipt: AttemptReceipt) -> None:
        persist_accepted(receipt)

    def apply_result(self, receipt: ResultReceipt) -> ResultApplication:
        return ResultApplication(applied=persist_result(receipt))

    def record_infrastructure_failure(self, receipt: InfrastructureFailureReceipt) -> None:
        persist_infrastructure_failure(receipt)

    def authorize_workspace(
        self,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        purpose: WorkspacePurpose,
    ) -> WorkspaceContext:
        actions = _WORKSPACE_ACTIONS.get(purpose) if isinstance(purpose, str) else None
        if actions is None:
            raise _not_found()

        match = Match.objects.filter(pk=match_id, kind=Match.Kind.PLAYED).first()
        run = MatchRun.objects.filter(pk=run_id, match_id=match_id).first()
        if match is None or run is None:
            raise _not_found()
        try:
            _run_problem_entry(run, problem_id)
        except CompetitionSnapshotUnavailable as error:
            raise CompetitionGatewayUnavailable() from error

        user = User.objects.filter(pk=actor_id, is_active=True).first()
        is_admin = bool(user is not None and user.role == User.Roles.ADMIN)
        actor = None
        if user is not None and user.role == User.Roles.PARTICIPANT:
            actor = TournamentParticipant.objects.filter(
                tournament_id=match.tournament_id,
                user_id=actor_id,
                user__is_active=True,
            ).first()
        is_participant = bool(
            actor is not None
            and actor.status == TournamentParticipant.Status.ACTIVE
            and actor.user_id in _frozen_participant_ids(run)
        )
        if is_admin:
            # Global admins may inspect statements, but never receive code actions.
            if purpose in ("draft", "history"):
                raise _not_found()
        elif not is_participant:
            raise _not_found()

        condition_available = is_admin or (
            run.started_at is not None
            and run.status
            in (
                MatchRun.Status.RUNNING,
                MatchRun.Status.PAUSED,
                MatchRun.Status.FINALIZING,
                MatchRun.Status.FINISHED,
                MatchRun.Status.TIED,
                MatchRun.Status.SUPERSEDED,
            )
        )
        allowed_actions = actions
        if purpose == "statement" and not condition_available:
            # Return an empty capability set until the server has started the run.
            allowed_actions = frozenset()

        if purpose == "draft" and is_participant:
            if run.status not in (MatchRun.Status.READY, MatchRun.Status.RUNNING, MatchRun.Status.PAUSED):
                allowed_actions = frozenset({"read_draft"})
            if run.status == MatchRun.Status.RUNNING:
                try:
                    submission_elapsed_ms(_clock_snapshot(run), timezone.now())
                except ClockError:
                    pass
                else:
                    allowed_actions = frozenset((*allowed_actions, "submit"))

        return WorkspaceContext(
            actor_id=actor_id,
            run_id=run.pk,
            problem_id=problem_id,
            allowed_actions=allowed_actions,
            condition_available=condition_available,
        )


def get_competition_gateway() -> DjangoCompetitionGateway:
    """Factory target for runtime owners; callers still wire it explicitly."""
    return DjangoCompetitionGateway()


def get_run_problem_snapshot_provider() -> DjangoCompetitionGateway:
    """Factory target for the trusted worker's immutable run assignment lookup."""
    return DjangoCompetitionGateway()

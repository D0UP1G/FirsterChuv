"""Participant statement and language endpoints pinned to the frozen run."""

from __future__ import annotations

from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.competition.gateway import (
    CompetitionSnapshotUnavailable,
    get_run_problem_snapshot_provider,
)
from backend.apps.competition.models import Match
from backend.apps.drafts.errors import WorkspaceUnavailable
from backend.apps.drafts.factory import get_workspace_access

from . import compilers
from .catalog import DjangoProblemCatalog
from .errors import ProblemNotReady


class ConditionNotAvailable(APIException):
    status_code = 409
    default_code = "condition_not_available"
    default_detail = "Условие откроется после старта матча."


class WorkspaceProblemUnavailable(APIException):
    status_code = 503
    default_code = "workspace_unavailable"
    default_detail = "Условие задачи временно недоступно."


class PinnedProblemView(APIView):
    """Authorize through WorkspaceAccess, then read the exact version frozen into the run."""

    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def pinned_version(self, request, match_id: UUID, problem_id: UUID):
        match = get_object_or_404(Match.objects.filter(kind=Match.Kind.PLAYED), pk=match_id)
        run_id = match.current_run_id
        if run_id is None:
            raise NotFound("Матч ещё не настроен.")
        try:
            context = get_workspace_access().authorize_workspace(
                request.user.pk, match_id, run_id, problem_id, purpose="statement"
            )
        except WorkspaceUnavailable as error:
            raise WorkspaceProblemUnavailable() from error
        if not context.condition_available:
            raise ConditionNotAvailable()
        try:
            snapshot = get_run_problem_snapshot_provider().resolve(run_id, problem_id)
            return DjangoProblemCatalog().describe_pinned(
                problem_id, snapshot.problem_version, snapshot.problem_checksum
            )
        except (CompetitionSnapshotUnavailable, ProblemNotReady) as error:
            raise WorkspaceProblemUnavailable() from error


class MatchProblemStatementView(PinnedProblemView):
    def get(self, request, match_id: UUID, problem_id: UUID):
        version = self.pinned_version(request, match_id, problem_id)
        return Response(
            {
                "problemId": str(version.problem_id),
                "label": version.label,
                "version": version.version,
                "conditionAvailable": True,
                "title": version.title,
                "statementMarkdown": version.statement_markdown,
                "assetIds": list(version.asset_ids),
                "examples": [{"input": item.input, "output": item.output} for item in version.examples],
                "timeLimitMs": version.time_limit_ms,
                "memoryLimitBytes": version.memory_limit_bytes,
            }
        )


class MatchProblemLanguagesView(PinnedProblemView):
    def get(self, request, match_id: UUID, problem_id: UUID):
        version = self.pinned_version(request, match_id, problem_id)
        # Only compilers that were really verified are offered; the manifest alone is not trusted.
        registry = compilers.COMPILERS
        return Response(
            [
                {"id": item.id, "name": item.name, "template": item.template}
                for item in version.languages
                if (spec := registry.get(item.id)) is not None and spec.verified
            ]
        )

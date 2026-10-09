"""Narrow consumer port for the shared A2 workspace authorization contract."""

from typing import Protocol
from uuid import UUID

from backend.apps.common.contracts import WorkspaceAction, WorkspaceContext, WorkspacePurpose


class WorkspaceAccess(Protocol):
    def authorize_workspace(
        self,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        purpose: WorkspacePurpose,
    ) -> WorkspaceContext: ...

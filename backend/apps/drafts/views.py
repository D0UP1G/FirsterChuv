"""Private draft API; all object access is authorized through WorkspaceAccess."""

from uuid import UUID

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts.permissions import IsParticipant
from backend.apps.common.contracts import WorkspaceAction
from backend.apps.drafts.errors import (
    DraftError,
    DraftRevisionConflict,
    DraftStorageBusy,
    WorkspaceDenied,
    WorkspaceUnavailable,
)
from backend.apps.drafts.factory import get_workspace_access
from backend.apps.drafts.serializers import DraftUpdateSerializer
from backend.apps.drafts.services import DraftService, DraftSnapshot


class DraftAccessUnavailable(APIException):
    status_code = 503
    default_code = "workspace_unavailable"
    default_detail = "Рабочая область временно недоступна."


class DraftSaveUnavailable(APIException):
    status_code = 503
    default_code = "draft_busy"
    default_detail = "Сохранение черновика временно занято; повторите запрос."


def _draft_data(draft: DraftSnapshot) -> dict[str, object]:
    return {
        "run_id": draft.run_id,
        "problem_id": draft.problem_id,
        "language_id": draft.language_id,
        "source": draft.source,
        "revision": draft.revision,
        "updated_at": draft.updated_at,
    }


class PrivateDraftAPIView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def authorize(
        self,
        *,
        actor_id: UUID,
        match_id: UUID,
        run_id: UUID,
        problem_id: UUID,
        required_action: WorkspaceAction,
    ):
        access = get_workspace_access()
        context = access.authorize_workspace(
            actor_id,
            match_id,
            run_id,
            problem_id,
            purpose="draft",
        )
        allowed_actions = getattr(context, "allowed_actions", None)
        if (
            getattr(context, "actor_id", None) != actor_id
            or getattr(context, "run_id", None) != run_id
            or getattr(context, "problem_id", None) != problem_id
            or not isinstance(allowed_actions, (set, frozenset, tuple, list))
            or required_action not in allowed_actions
        ):
            raise WorkspaceDenied("workspace is not available")
        return context


@method_decorator(csrf_protect, name="dispatch")
class MatchDraftView(PrivateDraftAPIView):
    def get(self, request, match_id: UUID, problem_id: UUID):
        run_id = request.query_params.get("runId")
        language_id = request.query_params.get("languageId")
        if run_id is None or language_id is None:
            raise ValidationError({"runId": "runId and languageId are required."})
        try:
            run_id = UUID(run_id)
            context = self.authorize(
                actor_id=request.user.pk,
                match_id=match_id,
                run_id=run_id,
                problem_id=problem_id,
                required_action="read_draft",
            )
            draft = DraftService.get_current(context=context, language_id=language_id)
            if draft is None:
                raise NotFound("Черновик не найден.")
        except WorkspaceDenied as error:
            raise NotFound("Черновик не найден.") from error
        except WorkspaceUnavailable as error:
            raise DraftAccessUnavailable() from error
        except (ValueError, DraftError) as error:
            raise ValidationError({"draft": str(error)}) from error
        return Response(_draft_data(draft))

    def put(self, request, match_id: UUID, problem_id: UUID):
        language_id = request.query_params.get("languageId")
        if language_id is None:
            raise ValidationError({"languageId": "languageId is required."})
        serializer = DraftUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            context = self.authorize(
                actor_id=request.user.pk,
                match_id=match_id,
                run_id=payload["run_id"],
                problem_id=problem_id,
                required_action="write_draft",
            )
            draft = DraftService.save(
                context=context,
                language_id=language_id,
                source=payload["source"],
                expected_revision=payload["expected_revision"],
            )
        except DraftRevisionConflict as error:
            return Response(
                {
                    "error": {
                        "code": "revision_conflict",
                        "message": "Черновик изменился после его чтения.",
                        "fields": {
                            "current_draft": _draft_data(error.current) if error.current else None
                        },
                    },
                    "request_id": getattr(request, "request_id", None),
                },
                status=409,
            )
        except DraftStorageBusy as error:
            raise DraftSaveUnavailable() from error
        except WorkspaceDenied as error:
            raise NotFound("Черновик не найден.") from error
        except WorkspaceUnavailable as error:
            raise DraftAccessUnavailable() from error
        except DraftError as error:
            raise ValidationError({"draft": str(error)}) from error
        return Response(_draft_data(draft))

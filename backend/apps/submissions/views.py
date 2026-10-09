"""Session-authenticated, author-private HTTP endpoints for submissions."""

from uuid import UUID

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from backend.apps.accounts.permissions import IsParticipant
from backend.apps.submissions.errors import (
    AdmissionBusy,
    IdempotencyConflict,
    IntegrationUnavailable,
    QueueFull,
    SubmissionError,
    SubmissionNotFound,
)
from backend.apps.submissions.factory import get_submission_service
from backend.apps.submissions.serializers import SubmissionCreateSerializer
from backend.apps.submissions.services import SubmissionMetadata


class SubmissionConflict(APIException):
    status_code = 409
    default_code = "submission_conflict"


class SubmissionUnavailable(APIException):
    status_code = 503
    default_code = "integration_unavailable"
    default_detail = "Приём посылок временно недоступен."


class SubmissionQueueBusy(APIException):
    status_code = 503
    default_code = "queue_busy"
    default_detail = "Очередь посылок временно занята; повторите запрос с тем же Idempotency-Key."


class SubmissionRateThrottle(ScopedRateThrottle):
    """Limit attempts per authenticated author and match, independent of IP."""

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        self.scope = getattr(view, "throttle_scope", None)
        if self.scope is None:
            return None
        ident = f"{request.user.pk}:{view.kwargs.get('match_id', '')}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


def _submission_metadata(record: SubmissionMetadata) -> dict[str, object]:
    return {
        "submission_id": record.id,
        "run_id": record.run_id,
        "status": record.status,
        "verdict": record.verdict,
        "received_at": record.received_at,
        "elapsed_ms": record.elapsed_ms,
    }


class PrivateSubmissionAPIView(APIView):
    permission_classes = [IsAuthenticated, IsParticipant]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


@method_decorator(csrf_protect, name="dispatch")
class MatchSubmissionsView(PrivateSubmissionAPIView):
    throttle_classes = [SubmissionRateThrottle]
    throttle_scope = "submission"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "POST" else []

    def post(self, request, match_id: UUID):
        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key is None:
            raise ValidationError({"Idempotency-Key": "This header is required."})
        try:
            record = get_submission_service().admit(
                actor_id=request.user.pk,
                match_id=match_id,
                run_id=serializer.validated_data["run_id"],
                problem_id=serializer.validated_data["problem_id"],
                language_id=serializer.validated_data["language_id"],
                source=serializer.validated_data["source"],
                idempotency_key=idempotency_key,
            )
        except IdempotencyConflict as error:
            raise SubmissionConflict(str(error), code="idempotency_conflict") from error
        except QueueFull as error:
            raise SubmissionConflict(str(error), code="queue_full") from error
        except IntegrationUnavailable as error:
            raise SubmissionUnavailable() from error
        except AdmissionBusy as error:
            raise SubmissionQueueBusy() from error
        except SubmissionError as error:
            raise ValidationError({"submission": str(error)}) from error
        return Response(_submission_metadata(record), status=202)

    def get(self, request, match_id: UUID):
        problem_id = request.query_params.get("problemId")
        if problem_id is not None:
            try:
                problem_id = UUID(problem_id)
            except (TypeError, ValueError) as error:
                raise ValidationError({"problemId": "A valid UUID is required."}) from error
        try:
            limit = int(request.query_params.get("limit", "25"))
            offset = int(request.query_params.get("offset", "0"))
        except ValueError as error:
            raise ValidationError({"pagination": "limit and offset must be integers."}) from error
        if not 1 <= limit <= 100 or offset < 0:
            raise ValidationError({"pagination": "limit must be 1–100 and offset non-negative."})
        results, count = get_submission_service().list_for_author(
            actor_id=request.user.pk,
            match_id=match_id,
            problem_id=problem_id,
            limit=limit,
            offset=offset,
        )
        return Response({"count": count, "results": [_submission_metadata(item) for item in results]})


class SubmissionDetailView(PrivateSubmissionAPIView):
    def get(self, request, submission_id: UUID):
        try:
            result = get_submission_service().get_author_metadata(
                actor_id=request.user.pk,
                submission_id=submission_id,
            )
        except SubmissionNotFound as error:
            raise NotFound("Посылка не найдена.") from error
        data = _submission_metadata(result.submission)
        data["compile_diagnostics"] = result.compile_diagnostics
        return Response(data)


class SubmissionSourceView(PrivateSubmissionAPIView):
    def get(self, request, submission_id: UUID):
        try:
            source = get_submission_service().get_source_for_author(
                actor_id=request.user.pk,
                submission_id=submission_id,
            )
        except SubmissionNotFound as error:
            raise NotFound("Посылка не найдена.") from error
        return Response({"submission_id": submission_id, "source": source})

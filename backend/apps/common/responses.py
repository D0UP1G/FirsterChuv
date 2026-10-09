"""Small Django response helpers shared by middleware and API endpoints."""

from django.http import JsonResponse


def api_error_response(request, *, code: str, message: str, status: int, fields=None):
    return JsonResponse(
        {
            "error": {"code": code, "message": message, "fields": fields},
            "requestId": str(getattr(request, "request_id", "")) or None,
        },
        status=status,
    )

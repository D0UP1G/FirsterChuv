from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from backend.apps.common.responses import api_error_response


def csrf_failure(request, reason=""):
    """Keep CSRF failures generic and in the same JSON API envelope."""
    return api_error_response(
        request,
        code="csrf_failed",
        message="CSRF verification failed.",
        status=403,
    )

@require_GET
def health(request):
    """Return minimal process/DB health without settings or version data."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})

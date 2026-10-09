from uuid import uuid4

from backend.apps.common.responses import api_error_response


class RequestIdMiddleware:
    """Attach a request correlation ID without exposing request contents."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid4()
        response = self.get_response(request)
        if response.status_code == 404 and (
            request.path == "/api/v1" or request.path.startswith("/api/v1/")
        ):
            response = api_error_response(
                request,
                code="not_found",
                message="Not found.",
                status=404,
            )
        if request.path.startswith("/api/v1/auth/") or request.path == "/api/v1/me":
            response["Cache-Control"] = "no-store"
        response["X-Request-ID"] = str(request.request_id)
        return response

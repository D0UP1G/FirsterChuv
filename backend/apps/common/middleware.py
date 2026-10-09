from uuid import uuid4

from django.http import JsonResponse


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
            response = JsonResponse(
                {
                    "error": {
                        "code": "not_found",
                        "message": "Not found.",
                        "fields": None,
                    },
                    "requestId": str(request.request_id),
                },
                status=404,
            )
        response["X-Request-ID"] = str(request.request_id)
        return response

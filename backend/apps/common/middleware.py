from uuid import uuid4


class RequestIdMiddleware:
    """Attach a request correlation ID without exposing request contents."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid4()
        response = self.get_response(request)
        response["X-Request-ID"] = str(request.request_id)
        return response

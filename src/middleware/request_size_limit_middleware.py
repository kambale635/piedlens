from django.conf import settings
from django.http import JsonResponse


class RequestSizeLimitMiddleware:
    """Reject requests declaring a body larger than the configured application limit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        content_length = request.META.get("CONTENT_LENGTH", "")
        if content_length:
            try:
                body_size = int(content_length)
            except ValueError:
                return self._error(request, 400, "INVALID_CONTENT_LENGTH")
            if body_size < 0:
                return self._error(request, 400, "INVALID_CONTENT_LENGTH")
            if body_size > settings.DJANGO_MAX_REQUEST_BODY_BYTES:
                return self._error(request, 413, "REQUEST_TOO_LARGE")
        return self.get_response(request)

    @staticmethod
    def _error(request, status, error_code):
        return JsonResponse(
            {
                "errorCode": error_code,
                "correlationId": getattr(request, "correlation_id", ""),
            },
            status=status,
        )
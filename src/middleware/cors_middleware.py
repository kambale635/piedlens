from django.conf import settings
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers


class CorsMiddleware:
    """Allow only exact configured origins and reject unauthorized preflight requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        allowed_origin = origin in settings.CORS_ALLOWED_ORIGINS
        requested_method = request.headers.get("Access-Control-Request-Method", "").upper()
        is_preflight = request.method == "OPTIONS" and bool(requested_method)

        if is_preflight:
            requested_headers = {
                value.strip().lower()
                for value in request.headers.get("Access-Control-Request-Headers", "").split(",")
                if value.strip()
            }
            allowed_headers = {header.lower() for header in settings.CORS_ALLOWED_HEADERS}
            if (
                not allowed_origin
                or requested_method not in settings.CORS_ALLOWED_METHODS
                or not requested_headers.issubset(allowed_headers)
            ):
                return HttpResponse(status=403)
            response = HttpResponse(status=204)
            response["Access-Control-Allow-Methods"] = ", ".join(settings.CORS_ALLOWED_METHODS)
            response["Access-Control-Allow-Headers"] = ", ".join(settings.CORS_ALLOWED_HEADERS)
        else:
            response = self.get_response(request)

        if origin:
            patch_vary_headers(response, ["Origin"])
        if allowed_origin:
            response["Access-Control-Allow-Origin"] = origin
        return response
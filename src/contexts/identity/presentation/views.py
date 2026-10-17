from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.serializers.json import DjangoJSONEncoder

from middleware.route_policy import public_route
from piedlens_platform.di.container import ApplicationContainer


def _body(request):
    import json

    return json.loads(request.body or b"{}")


@csrf_exempt
@public_route
@require_http_methods(["POST"])
def register(request):
    payload = _body(request)
    result = ApplicationContainer.register_user().execute(
        payload.get("phoneNumber", ""), payload.get("password", ""), payload.get("email")
    )
    return JsonResponse(result, status=201, encoder=DjangoJSONEncoder)


@csrf_exempt
@public_route
@require_http_methods(["POST"])
def login(request):
    payload = _body(request)
    result = ApplicationContainer.authenticate_user().execute(
        payload.get("phoneNumber", ""), payload.get("password", "")
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@csrf_exempt
@public_route
@require_http_methods(["POST"])
def refresh(request):
    result = ApplicationContainer.refresh_access_token().execute(_body(request).get("refreshToken", ""))
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@csrf_exempt
@public_route(authentication_required=True)
@require_http_methods(["POST"])
def create_merchant(request):
    payload = _body(request)
    result = ApplicationContainer.create_merchant().execute(
        acting_user_id=request.user.id,
        name=payload.get("name", ""),
        country=payload.get("country", ""),
        preferred_language=payload.get("preferredLanguage", ""),
        currency=payload.get("currency", ""),
    )
    return JsonResponse(result, status=201, encoder=DjangoJSONEncoder)
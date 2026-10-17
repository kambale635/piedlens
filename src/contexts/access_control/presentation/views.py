from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import requires_permission
from piedlens_platform.di.container import ApplicationContainer


def _body(request):
    import json

    return json.loads(request.body or b"{}")


@csrf_exempt
@requires_permission("role.create")
@require_http_methods(["POST"])
def create_role(request):
    payload = _body(request)
    result = ApplicationContainer.create_role().execute(
        payload.get("name", ""), payload.get("permissions", []), request.user.id
    )
    return JsonResponse(result, status=201, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("role.update")
@require_http_methods(["PUT"])
def update_role_permissions(request, role_id):
    result = ApplicationContainer.update_role_permissions().execute(
        UUID(str(role_id)), _body(request).get("permissions", []), request.user.id
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("role.assign")
@require_http_methods(["POST"])
def assign_role(request):
    payload = _body(request)
    result = ApplicationContainer.assign_role_to_user().execute(
        UUID(str(payload["userId"])),
        UUID(str(payload["roleId"])),
        payload["scope"],
        request.user.id,
    )
    return JsonResponse(result, status=201, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("role.revoke")
@require_http_methods(["DELETE"])
def revoke_role(request, role_assignment_id):
    result = ApplicationContainer.revoke_role_from_user().execute(
        UUID(str(role_assignment_id)), request.user.id
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)
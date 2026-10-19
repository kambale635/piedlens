import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import requires_global_permission
from middleware.route_policy import public_route
from .application_container import BillingContainer


@public_route
@require_http_methods(["GET"])
def pricing(request):
    result = BillingContainer.list_pricing().execute(request.GET.get("country", ""))
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_global_permission("plan.manage")
@require_http_methods(["PUT"])
def upsert_plan(request, code):
    payload = json.loads(request.body or b"{}")
    result = BillingContainer.upsert_plan().execute(
        code=code,
        is_active=payload.get("active", True),
        display_order=payload.get("order", 0),
        entitlements=payload.get("entitlements"),
    )
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_global_permission("plan.manage")
@require_http_methods(["PUT"])
def upsert_plan_price(request):
    payload = json.loads(request.body or b"{}")
    result = BillingContainer.upsert_plan_price().execute(
        plan_code=payload.get("planCode", ""),
        country=payload.get("country", ""),
        currency=payload.get("currency", ""),
        period_days=payload.get("periodDays", 0),
        amount_minor=payload.get("amountMinor", -1),
        is_active=payload.get("active", True),
    )
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder)
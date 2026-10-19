import json
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import requires_global_permission
from middleware.route_policy import public_route
from middleware.route_policy import requires_permission
from .application_container import BillingContainer
from piedlens_platform.di.container import ApplicationContainer


@public_route
@require_http_methods(["GET"])
def pricing(request):
    result = BillingContainer.list_pricing().execute(request.GET.get("country", ""))
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("billing.trial.start")
@require_http_methods(["POST"])
def start_trial(request):
    payload = json.loads(request.body or b"{}")
    result = BillingContainer.start_trial().execute(
        request.merchant_id, card_provided=payload.get("cardProvided", False)
    )
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder, status=201)


@csrf_exempt
@requires_permission("billing.coupon.apply")
@require_http_methods(["POST"])
def apply_coupon(request):
    payload = json.loads(request.body or b"{}")
    result = BillingContainer.apply_coupon().execute(
        request.merchant_id, payload.get("code", "")
    )
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("billing.referral.redeem")
@require_http_methods(["POST"])
def redeem_referral(request):
    payload = json.loads(request.body or b"{}")
    result = BillingContainer.redeem_referral().execute(
        request.merchant_id, _uuid(payload.get("referrerMerchantId"))
    )
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder, status=201)


@csrf_exempt
@requires_global_permission("plan.manage")
@require_http_methods(["PUT"])
def upsert_trial_policy(request):
    payload = json.loads(request.body or b"{}")
    result = BillingContainer.upsert_trial_policy().execute(
        payload.get("enabled", True),
        payload.get("durationDays", 14),
        payload.get("targetPlanCode", "starter"),
        payload.get("cardRequired", False),
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_global_permission("plan.manage")
@require_http_methods(["PUT"])
def upsert_referral_policy(request):
    payload = json.loads(request.body or b"{}")
    result = BillingContainer.upsert_referral_policy().execute(
        payload.get("rewardPercent", 10),
        payload.get("rewardDurationDays", 30),
        payload.get("maxReferrals", 10),
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_global_permission("plan.manage")
@require_http_methods(["PUT"])
def upsert_coupon(request):
    payload = json.loads(request.body or b"{}")
    valid_from = parse_datetime(payload.get("validFrom", ""))
    valid_until_value = payload.get("validUntil")
    valid_until = parse_datetime(valid_until_value) if valid_until_value else None
    result = BillingContainer.upsert_coupon().execute(
        payload.get("code", ""),
        payload.get("discountPercent", 0),
        payload.get("durationDays", 0),
        payload.get("maxRedemptions"),
        valid_from,
        valid_until,
        payload.get("active", True),
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_global_permission("plan.manage")
@require_http_methods(["PUT"])
def upsert_outbound_rate(request):
    payload = json.loads(request.body or b"{}")
    valid_from = parse_datetime(payload.get("validFrom", ""))
    valid_until_value = payload.get("validUntil")
    valid_until = parse_datetime(valid_until_value) if valid_until_value else None
    result = BillingContainer.upsert_outbound_rate().execute(
        payload.get("country", ""),
        payload.get("category", ""),
        payload.get("currency", ""),
        payload.get("amountMinor", -1),
        valid_from,
        valid_until,
        payload.get("active", True),
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@requires_permission("outbound.estimate")
@require_http_methods(["POST"])
def estimate_outbound(request):
    payload = json.loads(request.body or b"{}")
    result = ApplicationContainer.estimate_outbound_cost().execute(
        request.merchant_id,
        payload.get("category", ""),
        payload.get("count", 1),
    )
    return JsonResponse(result.__dict__, encoder=DjangoJSONEncoder)


@requires_permission("outbound.usage.read")
@require_http_methods(["GET"])
def outbound_usage(request):
    return JsonResponse(
        {"usage": BillingContainer.outbound_usage_reader().usage_for(request.merchant_id)},
        encoder=DjangoJSONEncoder,
    )


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


def _uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        from contexts.billing.application.exceptions import ReferralNotValidException

        raise ReferralNotValidException("Referral merchant identifier is invalid.")
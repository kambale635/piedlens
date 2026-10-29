import json
from datetime import datetime, timezone

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import public_route, requires_global_permission, requires_permission
from piedlens_platform.di.container import ApplicationContainer
from shared_kernel.application_exceptions import ValidationException


def _body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (ValueError, TypeError) as error:
        raise ValidationException("Request body must be valid JSON.") from error
    if not isinstance(value, dict):
        raise ValidationException("Request body must be a JSON object.")
    return value


@csrf_exempt
@requires_permission("payment.start")
@require_http_methods(["POST"])
def start_payment(request):
    payload = _body(request)
    idempotency_key = request.headers.get("Idempotency-Key", "")
    result = ApplicationContainer.start_payment().execute(
        merchant_id=request.merchant_id,
        payable_type=payload.get("payableType", "subscription"),
        payable_id=payload.get("payableId", request.merchant_id),
        method=payload.get("method", "manual"),
        idempotency_key=idempotency_key,
        payable_options={
            "plan_code": payload.get("planCode", ""),
            "period_days": payload.get("periodDays", 30),
        },
    )
    return JsonResponse(result, status=200 if result.get("duplicate") else 201, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_global_permission("payment.route.manage")
@require_http_methods(["PUT"])
def configure_payment_route(request):
    payload = _body(request)
    result = ApplicationContainer.configure_payment_route().execute(
        country=payload.get("country", ""), currency=payload.get("currency", ""),
        method=payload.get("method", ""), provider_code=payload.get("providerCode", ""),
        priority=payload.get("priority", 100), active=payload.get("active", True),
        supports_escrow=payload.get("supportsEscrow", False), config=payload.get("config") or {},
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


@csrf_exempt
@public_route
@require_http_methods(["POST"])
def payment_webhook(request, provider_code):
    timestamp = request.headers.get("X-Webhook-Timestamp", "")
    signature = request.headers.get("X-Payment-Signature", "")
    try:
        if timestamp.isascii() and timestamp.isdigit():
            sent_at = datetime.fromtimestamp(int(timestamp), timezone.utc)
        else:
            sent_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError) as error:
        raise ValidationException("Webhook timestamp is invalid.") from error
    tolerance = settings.PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS
    if abs((datetime.now(timezone.utc) - sent_at.astimezone(timezone.utc)).total_seconds()) > tolerance:
        raise ValidationException("Webhook timestamp is outside the accepted tolerance.")
    result = ApplicationContainer.handle_payment_webhook().execute(
        provider_code=provider_code,
        raw_body=request.body,
        signature=signature,
        timestamp=timestamp,
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)

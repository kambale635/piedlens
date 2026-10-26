import json
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import public_route, requires_permission
from piedlens_platform.di.container import ApplicationContainer


@csrf_exempt
@requires_permission("platform.connect")
@require_http_methods(["POST"])
def connect_platform(request):
    payload = json.loads(request.body or b"{}")
    result = ApplicationContainer.connect_platform().execute(
        merchant_id=request.merchant_id,
        platform_type=payload.get("platformType", ""),
        oauth_code=payload.get("oauthCode", ""),
        external_account_id=payload.get("externalAccountId"),
        consent_given=payload.get("consentGiven") is True,
    )
    return JsonResponse(
        {
            "id": result["platform_connection_id"],
            "platformType": payload.get("platformType"),
            "connectionStatus": result["connection_status"],
        },
        status=201,
        encoder=DjangoJSONEncoder,
    )


@csrf_exempt
@requires_permission("message.import")
@require_http_methods(["POST"])
def submit_conversation_import(request):
    payload = json.loads(request.body or b"{}")
    result = ApplicationContainer.submit_conversation_import().execute(
        merchant_id=request.merchant_id,
        format_code=payload.get("formatCode", ""),
        content=payload.get("content", ""),
        consent_id=UUID(str(payload.get("consentId", ""))),
        consent=payload.get("consentGiven") is True,
        selected_range=payload.get("selectedRange") or {},
    )
    return JsonResponse(
        {"importId": result.import_id, "status": result.status, "duplicate": result.duplicate},
        status=202,
        encoder=DjangoJSONEncoder,
    )


@requires_permission("message.import")
@require_http_methods(["GET"])
def get_conversation_import(request, import_id):
    result = ApplicationContainer.get_conversation_import().execute(
        request.merchant_id, import_id
    )
    return JsonResponse(result, encoder=DjangoJSONEncoder)


def _webhook(request, platform_type):
    result = ApplicationContainer.handle_incoming_webhook().execute(
        platform_type=platform_type,
        raw_body=request.body,
        signature=request.headers.get("X-Hub-Signature-256", ""),
        timestamp=request.headers.get("X-Webhook-Timestamp", ""),
    )
    return JsonResponse({"accepted": True, "messageCount": result["accepted_count"]})


@csrf_exempt
@public_route
@require_http_methods(["POST"])
def whatsapp_webhook(request):
    return _webhook(request, "whatsapp")


@csrf_exempt
@public_route
@require_http_methods(["POST"])
def instagram_webhook(request):
    return _webhook(request, "instagram")
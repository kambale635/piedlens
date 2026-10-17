import json
from dataclasses import asdict
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import requires_permission
from piedlens_platform.di.container import ApplicationContainer


def _body(request):
    return json.loads(request.body or b"{}")


def _merchant_id(request):
    return UUID(str(request.merchant_id))


def _page(request, name, default):
    return int(request.GET.get(name, default))


@requires_permission("order.read")
@require_http_methods(["GET"])
def dormant_money_dashboard(request):
    result = ApplicationContainer.get_dormant_money_dashboard().execute(
        _merchant_id(request),
        older_than_hours=_page(request, "olderThanHours", 24),
    )
    totals = [asdict(money) for money in result.totals_by_currency]
    response = {
        "totalsByCurrency": totals,
        "orders": [
            {
                "id": order.order_id,
                "contactId": order.contact_id,
                "amount": asdict(order.amount),
                "status": order.status,
                "createdAt": order.created_at,
            }
            for order in result.orders
        ],
    }
    if len(totals) == 1:
        response["totalDormantAmount"] = totals[0]
    return JsonResponse(response, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("order.update_status")
@require_http_methods(["PATCH"])
def update_order_status(request, order_id):
    result = ApplicationContainer.update_order_status().execute(
        UUID(str(order_id)),
        _body(request).get("newStatus", ""),
        "merchant",
        merchant_id=_merchant_id(request),
    )
    return JsonResponse(
        {"orderId": result.order_id, "status": result.status, "updatedAt": result.updated_at},
        encoder=DjangoJSONEncoder,
    )


@csrf_exempt
@requires_permission("order.remind")
@require_http_methods(["POST"])
def schedule_reminder(request, order_id):
    payload = _body(request)
    result = ApplicationContainer.schedule_reminder().execute(
        UUID(str(order_id)),
        payload.get("reminderType", ""),
        payload.get("customMessage"),
        merchant_id=_merchant_id(request),
    )
    return JsonResponse(
        {"reminderId": result.reminder_id, "scheduledFor": result.scheduled_for},
        status=201,
        encoder=DjangoJSONEncoder,
    )


@requires_permission("order.review")
@require_http_methods(["GET"])
def list_pending_detection_candidates(request):
    result = ApplicationContainer.list_pending_detection_candidates().execute(
        merchant_id=_merchant_id(request),
        page=_page(request, "page", 1),
        page_size=_page(request, "pageSize", 50),
    )
    return JsonResponse(
        {
            "candidates": [
                {
                    "candidateId": candidate.candidate_id,
                    "contactId": candidate.contact_id,
                    "detectedAmount": asdict(candidate.detected_amount),
                    "confidenceScore": candidate.confidence_score.value,
                    "sourceMessageId": candidate.source_message_id,
                    "createdAt": candidate.created_at,
                }
                for candidate in result.candidates
            ],
            "totalCount": result.total_count,
        },
        encoder=DjangoJSONEncoder,
    )


@csrf_exempt
@requires_permission("order.review")
@require_http_methods(["POST"])
def decide_detection_candidate(request, candidate_id):
    result = ApplicationContainer.validate_or_reject_detection().execute(
        candidate_id=UUID(str(candidate_id)),
        decision=_body(request).get("decision", ""),
        merchant_id=_merchant_id(request),
    )
    return JsonResponse(
        {"candidateId": result.candidate_id, "status": result.status},
        encoder=DjangoJSONEncoder,
    )
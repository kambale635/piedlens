import json
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import requires_permission
from piedlens_platform.di.container import ApplicationContainer


def _body(request):
    return json.loads(request.body or b"{}")


def _page(request, name, default):
    return int(request.GET.get(name, default))


def _contacts_response(result):
    return {
        "contacts": [
            {
                "contactId": contact["contact_id"],
                "displayName": contact["display_name"],
                "externalIdentifier": contact["external_identifier"],
                "loyaltyScore": contact["loyalty_score"],
                "orderCount": contact["order_count"],
            }
            for contact in result["contacts"]
        ],
        "totalCount": result["total_count"],
    }


@requires_permission("contact.read")
@require_http_methods(["GET"])
def list_contacts(request):
    segment_id = request.GET.get("segment")
    result = ApplicationContainer.list_crm_contacts().execute(
        merchant_id=UUID(str(request.merchant_id)),
        segment_id=UUID(segment_id) if segment_id else None,
        page=_page(request, "page", 1),
        page_size=_page(request, "pageSize", 50),
    )
    return JsonResponse(_contacts_response(result), encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("contact.merge")
@require_http_methods(["POST"])
def merge_contacts(request):
    payload = _body(request)
    result = ApplicationContainer.merge_contacts().execute(
        primary_contact_id=UUID(str(payload["primaryContactId"])),
        duplicate_contact_id=UUID(str(payload["duplicateContactId"])),
        merchant_id=UUID(str(request.merchant_id)),
    )
    return JsonResponse(
        {
            "primaryContactId": result.primary_contact_id,
            "mergedContactId": result.merged_contact_id,
            "status": result.status,
        },
        status=202,
        encoder=DjangoJSONEncoder,
    )


@csrf_exempt
@requires_permission("segment.create")
@require_http_methods(["POST"])
def create_segment(request):
    payload = _body(request)
    result = ApplicationContainer.create_crm_segment().execute(
        merchant_id=UUID(str(request.merchant_id)),
        name=payload.get("name", ""),
        definition_rule=payload.get("definitionRule", {}),
    )
    return JsonResponse({"segmentId": result["segment_id"]}, status=201, encoder=DjangoJSONEncoder)


@requires_permission("contact.read")
@require_http_methods(["GET"])
def get_segment_members(request, segment_id):
    result = ApplicationContainer.get_crm_segment_members().execute(
        segment_id=UUID(str(segment_id)),
        page=_page(request, "page", 1),
        page_size=_page(request, "pageSize", 50),
        merchant_id=UUID(str(request.merchant_id)),
    )
    return JsonResponse(_contacts_response(result), encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("segment.bulk_message")
@require_http_methods(["POST"])
def send_bulk_message(request, segment_id):
    payload = _body(request)
    result = ApplicationContainer.send_bulk_message().execute(
        segment_id=UUID(str(segment_id)),
        template=payload.get("template", ""),
        channel=payload.get("channel", ""),
        merchant_id=UUID(str(request.merchant_id)),
    )
    return JsonResponse(
        {
            "bulkMessageLogId": result.bulk_message_log_id,
            "status": result.status,
            "recipientCount": result.recipient_count,
        },
        status=202,
        encoder=DjangoJSONEncoder,
    )
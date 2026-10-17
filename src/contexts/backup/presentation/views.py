import json
from datetime import datetime
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from contexts.backup.application.exceptions import InvalidExportSignatureException
from contexts.backup.infrastructure.persistence.django_object_storage import DjangoObjectStorage
from middleware.route_policy import public_route, requires_permission
from piedlens_platform.di.container import ApplicationContainer


def _page(request, name, default):
    return int(request.GET.get(name, default))


@requires_permission("backup.read")
@require_http_methods(["GET"])
def list_backups(request):
    result = ApplicationContainer.list_backups().execute(
        merchant_id=UUID(str(request.merchant_id)),
        platform_connection_id=(
            UUID(request.GET["platformConnectionId"])
            if request.GET.get("platformConnectionId")
            else None
        ),
        page=_page(request, "page", 1),
        page_size=_page(request, "pageSize", 50),
    )
    return JsonResponse(
        {
            "snapshots": [
                {
                    "id": snapshot.id,
                    "platformConnectionId": snapshot.platform_connection_id,
                    "snapshotDate": snapshot.snapshot_date,
                    "status": snapshot.status.value,
                    "dataIntegrityHash": snapshot.data_integrity_hash,
                    "messageCount": snapshot.message_count,
                    "mediaCount": snapshot.media_count,
                }
                for snapshot in result["snapshots"]
            ],
            "totalCount": result["total_count"],
        },
        encoder=DjangoJSONEncoder,
    )


@csrf_exempt
@requires_permission("backup.restore")
@require_http_methods(["POST"])
def restore_from_snapshot(request, platform_connection_id):
    payload = json.loads(request.body or b"{}")
    as_of_date = payload.get("asOfDate")
    if as_of_date:
        as_of_date = datetime.fromisoformat(as_of_date.replace("Z", "+00:00"))
    result = ApplicationContainer.restore_from_snapshot().execute(
        platform_connection_id=UUID(str(platform_connection_id)),
        as_of_date=as_of_date,
        merchant_id=UUID(str(request.merchant_id)),
    )
    return JsonResponse(
        {"exportJobId": result["export_job_id"], "status": result["status"]},
        status=202,
        encoder=DjangoJSONEncoder,
    )


@requires_permission("backup.read")
@require_http_methods(["GET"])
def get_backup_export(request, export_job_id):
    result = ApplicationContainer.get_backup_export().execute(
        merchant_id=UUID(str(request.merchant_id)),
        export_job_id=UUID(str(export_job_id)),
    )
    response = {"status": result["status"]}
    if result.get("download_url"):
        response["downloadUrl"] = result["download_url"]
        response["expiresAt"] = result["expires_at"]
    return JsonResponse(response, encoder=DjangoJSONEncoder)


@csrf_exempt
@requires_permission("merchant.delete_data")
@require_http_methods(["DELETE"])
def delete_all_merchant_data(request, merchant_id):
    payload = json.loads(request.body or b"{}")
    result = ApplicationContainer.delete_all_merchant_data().execute(
        merchant_id=UUID(str(request.merchant_id)),
        confirmation_token=payload.get("confirmationToken", ""),
    )
    return JsonResponse({"deletedAt": result["deleted_at"]}, encoder=DjangoJSONEncoder)


@public_route
@require_http_methods(["GET"])
def download_backup_object(request, reference):
    """Serve a stored export only when its signed bearer URL is valid and unexpired."""
    storage = DjangoObjectStorage()
    if not storage.verify_signed_url(
        reference,
        request.GET.get("expires", ""),
        request.GET.get("signature", ""),
    ):
        raise InvalidExportSignatureException("Backup export signature is invalid or expired.")
    return JsonResponse(storage.retrieve(reference), encoder=DjangoJSONEncoder)
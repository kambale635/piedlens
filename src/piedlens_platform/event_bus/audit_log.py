from .models import AuditLogRecord


class DjangoAuditLogSink:
    """Persist only request identifiers and access outcomes, never request content."""

    def __call__(self, event: dict) -> None:
        AuditLogRecord.objects.create(
            correlation_id=str(event.get("correlation_id") or "")[:128],
            user_id=str(event.get("user_id") or "")[:64],
            merchant_id=str(event.get("merchant_id") or "")[:64],
            permission=event.get("permission"),
            outcome=str(event.get("outcome") or "unknown")[:32],
            route=str(event.get("route") or "")[:512],
        )
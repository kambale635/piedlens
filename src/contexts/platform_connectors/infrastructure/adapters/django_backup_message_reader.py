from uuid import UUID

from django.db.models import QuerySet

from ..persistence.models import MessageRecord


class DjangoBackupMessageReader:
    """Expose normalized message deltas to Backup without importing that context (INV-TR-04)."""

    def read_messages(self, connection_id: UUID, since=None) -> list[dict]:
        """Return serializable messages for one connection after the prior snapshot."""
        records: QuerySet = MessageRecord.objects.filter(platform_connection_id=connection_id)
        if since is not None:
            records = records.filter(received_at__gt=since)
        return list(
            records.order_by("received_at", "id").values(
                "id",
                "external_message_id",
                "external_sender_id",
                "display_name",
                "text_content",
                "received_at",
            )
        )
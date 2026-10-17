from uuid import UUID

from django.db.models import QuerySet

from ..persistence.models import ContactRecord


class DjangoBackupContactReader:
    """Expose CRM-owned contact deltas through a shared port without Backup imports (INV-TR-04)."""

    def read_contacts(self, merchant_id: UUID, connection_id: UUID, since=None) -> list[dict]:
        """Return serializable contact state updated after the last snapshot."""
        records: QuerySet = ContactRecord.objects.filter(
            merchant_id=merchant_id,
            platform_connection_id=connection_id,
        )
        if since is not None:
            records = records.filter(last_interaction_at__gt=since)
        return list(
            records.order_by("id").values(
                "id",
                "external_identifier",
                "display_name",
                "total_spent_by_currency",
                "order_count",
                "last_interaction_at",
                "purchase_history",
                "loyalty_score",
                "tags",
                "status",
            )
        )
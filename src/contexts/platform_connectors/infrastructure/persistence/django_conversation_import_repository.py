from uuid import UUID

from .models import ConversationImportRecord


class DjangoConversationImportRepository:
    """Persist and query imports within the owning merchant boundary (INV-IMP-01/02)."""

    def __init__(self, cipher):
        self._cipher = cipher

    def create_if_new(self, values: dict) -> tuple[UUID, bool]:
        record, created = ConversationImportRecord.objects.get_or_create(
            merchant_id=values["merchant_id"],
            content_hash=values["content_hash"],
            defaults={**values, "status": "queued"},
        )
        return record.id, created

    def status_for_merchant(self, import_id: UUID, merchant_id: UUID) -> dict | None:
        record = ConversationImportRecord.objects.filter(id=import_id, merchant_id=merchant_id).first()
        if record is None:
            return None
        return {
            "import_id": record.id,
            "status": record.status,
            "accepted_count": record.accepted_count,
            "rejected_count": record.rejected_count,
            "errors": record.errors,
        }

    def content_for_processing(self, record: ConversationImportRecord) -> str:
        """Decrypt queued content only for the asynchronous worker (INV-IMP-04)."""
        return self._cipher.decrypt(record.encrypted_content)

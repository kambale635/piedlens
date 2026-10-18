from uuid import UUID

from .models import ProcessedEventRecord


class DjangoProcessedEventRepository:
    """Read and write the Rules Engine consumer ledger (INV-TR-03)."""

    def has_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Check the unique event/consumer key before applying a correction/evaluation."""
        return ProcessedEventRecord.objects.filter(
            event_id=event_id, consumer_name=consumer_name
        ).exists()

    def mark_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Persist the idempotency marker in the caller's transaction."""
        _, created = ProcessedEventRecord.objects.get_or_create(
            event_id=event_id,
            consumer_name=consumer_name,
        )
        return created
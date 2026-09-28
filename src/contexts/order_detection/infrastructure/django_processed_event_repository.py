"""Module: contexts/order_detection/infrastructure/django_processed_event_repository.py
Context: Order Detection.
Role: persist the consumer idempotency ledger in PostgreSQL.
"""

from uuid import UUID

from .models import ProcessedEventRecord


class DjangoProcessedEventRepository:
    """Implement processed-event checks and writes on the active Django transaction."""

    def has_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Check the unique event/consumer key required by INV-TR-03."""
        return ProcessedEventRecord.objects.filter(
            event_id=event_id, consumer_name=consumer_name
        ).exists()

    def mark_processed(self, event_id: UUID, consumer_name: str) -> None:
        """Insert an idempotency marker; callers must use the consumer UnitOfWork."""
        ProcessedEventRecord.objects.create(
            event_id=event_id,
            consumer_name=consumer_name,
        )
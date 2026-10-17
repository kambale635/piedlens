"""Module: contexts/crm/infrastructure/django_processed_message_repository.py
Context: CRM.
Role: persist MessageReceived consumer idempotency markers.
"""

from uuid import UUID

from ..persistence.models import ProcessedMessageRecord


class DjangoProcessedMessageRepository:
    """Implement the CRM processed-event ledger in the active database transaction."""

    def has_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Check the unique event and CRM-consumer key (INV-TR-03)."""
        return ProcessedMessageRecord.objects.filter(
            event_id=event_id,
            consumer_name=consumer_name,
        ).exists()

    def mark_processed(self, event_id: UUID, consumer_name: str) -> None:
        """Insert the processed marker atomically with the Contact aggregate."""
        ProcessedMessageRecord.objects.get_or_create(
            event_id=event_id,
            consumer_name=consumer_name,
        )
"""Module: contexts/platform_connectors/infrastructure/persistence/django_processed_event_repository.py
Context: Platform Connectors
Role: persist consumer idempotency markers in the same transaction as Outbox completion (INV-TR-03).
"""

from .models import ProcessedEventRecord


class DjangoPlatformConnectorsProcessedEventRepository:
    """Persist Platform Connectors event-consumer markers (INV-TR-03)."""

    def has_processed(self, event_id, consumer_name: str) -> bool:
        """Check whether this consumer already committed the event (INV-TR-03)."""
        return ProcessedEventRecord.objects.filter(
            event_id=event_id,
            consumer_name=consumer_name,
        ).exists()

    def mark_processed(self, event_id, consumer_name: str) -> bool:
        """Record event completion in the active transaction (INV-TR-03)."""
        _, created = ProcessedEventRecord.objects.get_or_create(
            event_id=event_id,
            consumer_name=consumer_name,
        )
        return created
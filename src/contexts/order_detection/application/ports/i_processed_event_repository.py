from typing import Protocol
from uuid import UUID


class IProcessedEventRepository(Protocol):
    """Persistence port for consumer idempotency records (INV-TR-03)."""

    def has_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Check whether this consumer committed the event previously."""

    def mark_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Record processing in the same transaction as aggregate and outbox writes."""
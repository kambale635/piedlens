from typing import Protocol
from uuid import UUID

from ..domain.relationship_anomaly_policy import RelationshipAnomalyPolicy


class ICRMUnitOfWork(Protocol):
    """Transaction boundary for one CRM aggregate and its consumer ledger marker."""

    def __enter__(self) -> "ICRMUnitOfWork":
        """Begin the CRM database transaction."""

    def __exit__(self, exception_type, exception, traceback) -> bool | None:
        """Commit on success or roll back all CRM writes on failure."""


class IProcessedMessageRepository(Protocol):
    """Idempotency ledger for the CRM MessageReceived consumer (INV-TR-03)."""

    def has_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Check the event/consumer key before applying a message event."""

    def mark_processed(self, event_id: UUID, consumer_name: str) -> None:
        """Write the marker in the Contact transaction."""


class ICRMOutbox(Protocol):
    """CRM-owned port for transactional producer events (INV-TR-02)."""

    def add(self, event: object) -> None:
        """Append one event to the active CRM database transaction."""


class IRelationshipAnomalyConfiguration(Protocol):
    """Resolve configured anomaly thresholds for one merchant (INV-CRM-05)."""

    def for_merchant(self, merchant_id: UUID) -> RelationshipAnomalyPolicy:
        """Return settings defaults with any configured merchant override."""


class ICRMClock(Protocol):
    """Application clock port for deterministic CRM scheduled jobs."""

    def now_utc(self):
        """Return the current timezone-aware UTC instant."""
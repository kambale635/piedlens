from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...domain.events.order_detection_events import (
    DetectionCandidateCreated,
    DetectionCandidatePromoted,
    DetectionCandidateRejected,
    DetectionCorrectedByMerchant,
    OrderDetected,
    OrderStatusChanged,
    ReminderCancelled,
    ReminderDeliveryFailed,
    ReminderProposed,
    ReminderSent,
    ReminderScheduled,
)

OrderDetectionEvent = (
    DetectionCandidateCreated
    | DetectionCandidatePromoted
    | DetectionCandidateRejected
    | DetectionCorrectedByMerchant
    | OrderDetected
    | OrderStatusChanged
    | ReminderScheduled
    | ReminderSent
    | ReminderProposed
    | ReminderCancelled
    | ReminderDeliveryFailed
)


class IClock(Protocol):
    """Provides the current UTC instant to application operations."""

    def now(self) -> datetime:
        """Return a timezone-aware current instant."""


class IOrderStatusIntentReader(Protocol):
    """Read the configured Rules Engine intent labels used by Order Detection (INV-RE-04)."""

    def configured_intents(self, merchant_id: UUID) -> frozenset[str]:
        """Return active status intent labels configured for the merchant."""


class IOrderDetectionUnitOfWork(Protocol):
    """Defines the transaction boundary for an Order Detection aggregate and outbox."""

    def __enter__(self) -> "IOrderDetectionUnitOfWork":
        """Begin the producer-context database transaction."""

    def __exit__(self, exception_type, exception, traceback) -> bool | None:
        """Commit on success or roll back on failure."""

    def lock_order(self, order_id: UUID) -> None:
        """Serialize concurrent transitions of one Order aggregate."""

    def lock_detection_contact(self, contact_id: UUID) -> None:
        """Serialize detections and correlation for one contact."""

    def lock_reminder(self, reminder_id: UUID) -> None:
        """Serialize finalization of one claimed Reminder."""


class IPromotedCandidateOrderUnitOfWork(Protocol):
    """Transaction boundary for idempotency, new Order and its outbox event."""

    def __enter__(self) -> "IPromotedCandidateOrderUnitOfWork":
        """Begin the consumer transaction."""

    def __exit__(self, exception_type, exception, traceback) -> bool | None:
        """Commit all consumer writes together or roll them back."""

    def lock_candidate_creation(self, candidate_id: UUID) -> None:
        """Serialize concurrent deliveries for one promoted candidate."""

    def lock_detection_contact(self, contact_id: UUID) -> None:
        """Serialize a promoted Order against Contact merge reconciliation."""


class IOrderDetectionOutbox(Protocol):
    """Port for appending domain events to the transactional outbox table."""

    def add(self, event: OrderDetectionEvent) -> None:
        """Append an event in the active aggregate transaction (INV-TR-02)."""


class IOrderDetectionMerchantPurger(Protocol):
    """Local persistence port for resumable merchant deletion (INV-OD-08)."""

    def purge_merchant_data(self, event_id: UUID, merchant_id: UUID) -> None: ...
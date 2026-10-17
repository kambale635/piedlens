from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.value_objects.money import Money

from ..value_objects.purchase_history_entry import PurchaseHistoryEntry


@dataclass(frozen=True)
class RelationshipAnomalyDetected:
    """CRM event emitted once per silence period through its transactional Outbox.

    Protects INV-CRM-06 and INV-TR-02.
    """

    merchant_id: UUID
    contact_id: UUID
    last_purchase_order_id: UUID
    days_since_last_purchase: float
    usual_interval_days: float
    occurred_at: datetime


@dataclass(frozen=True)
class MergedContactSnapshot:
    """Immutable duplicate Contact state captured in the tombstone transaction."""

    total_spent_by_currency: tuple[Money, ...]
    order_count: int
    purchase_history: tuple[PurchaseHistoryEntry, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ContactMerged:
    """CRM event carrying the tombstone snapshot to independent bounded contexts.

    Protects INV-CRM-03/07 and INV-TR-02. The event is written through CRM Outbox
    in the transaction that marks the duplicate Contact as merged.
    """

    event_id: UUID
    occurred_at: datetime
    merchant_id: UUID
    primary_contact_id: UUID
    merged_contact_id: UUID
    snapshot: MergedContactSnapshot


@dataclass(frozen=True)
class BulkMessageQueued:
    """Outbox event requesting asynchronous processing of a CRM campaign."""

    event_id: UUID
    occurred_at: datetime
    merchant_id: UUID
    campaign_id: UUID
    recipient_count: int


@dataclass(frozen=True)
class BulkMessageCompleted:
    """Outbox event emitted when all campaign recipient logs are terminal."""

    event_id: UUID
    occurred_at: datetime
    merchant_id: UUID
    campaign_id: UUID
    sent_count: int
    failed_count: int
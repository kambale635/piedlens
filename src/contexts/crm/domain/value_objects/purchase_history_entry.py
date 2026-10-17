from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PurchaseHistoryEntry:
    """CRM-owned fact identifying when one delivered purchase was recorded.

    The timestamp is copied from the `paid_and_delivered` OrderStatusChanged event;
    CRM owns this historical projection and never queries Order Detection tables.
    This history supports INV-CRM-05 while the source event is consumed idempotently
    under INV-TR-03.
    """

    order_id: UUID
    purchased_at: datetime
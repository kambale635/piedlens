from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RelationshipAnomalyNotification:
    """Immutable CRM alert record for one contact silence period (INV-CRM-06).

    `last_purchase_order_id` identifies the silence period: a later delivered
    purchase has a different order id and permits a new notification.
    """

    merchant_id: UUID
    contact_id: UUID
    last_purchase_order_id: UUID
    days_since_last_purchase: float
    usual_interval_days: float
    notified_at: datetime
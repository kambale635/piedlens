from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from statistics import median

from .purchase_history_entry import PurchaseHistoryEntry
from .relationship_anomaly_policy import RelationshipAnomalyPolicy


@dataclass(frozen=True)
class RelationshipAnomaly:
    """Measured anomaly data returned by the pure CRM domain detector."""

    days_since_last_purchase: Decimal
    usual_interval_days: Decimal


class RelationshipAnomalyDetector:
    """Apply configured purchase-history anomaly rules without I/O (INV-CRM-05)."""

    def detect(
        self,
        purchase_history: tuple[PurchaseHistoryEntry, ...],
        now: datetime,
        policy: RelationshipAnomalyPolicy,
    ) -> RelationshipAnomaly | None:
        """Return measurements only when history, multiplier, and floor all qualify."""
        ordered_history = sorted(
            purchase_history,
            key=lambda entry: (entry.purchased_at, str(entry.order_id)),
        )
        if len(ordered_history) < policy.min_purchases:
            return None

        intervals = [
            Decimal(str((current.purchased_at - previous.purchased_at).total_seconds()))
            / Decimal(86400)
            for previous, current in zip(ordered_history, ordered_history[1:])
        ]
        usual_interval_days = Decimal(str(median(intervals)))
        days_since_last_purchase = max(
            Decimal(0),
            Decimal(str((now - ordered_history[-1].purchased_at).total_seconds()))
            / Decimal(86400),
        )

        if (
            days_since_last_purchase
            <= usual_interval_days * policy.anomaly_multiplier
            or days_since_last_purchase < policy.min_inactivity_days
        ):
            return None

        return RelationshipAnomaly(
            days_since_last_purchase=days_since_last_purchase,
            usual_interval_days=usual_interval_days,
        )
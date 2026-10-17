from typing import Protocol

from ..entities.relationship_anomaly_notification import RelationshipAnomalyNotification


class IRelationshipAnomalyNotificationRepository(Protocol):
    """Persistence port for the CRM's one-alert-per-silence ledger (INV-CRM-06)."""

    def save_if_absent(self, notification: RelationshipAnomalyNotification) -> bool:
        """Persist once per contact and last-purchase id; return whether it was created."""
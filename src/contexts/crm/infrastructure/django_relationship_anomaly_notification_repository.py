"""Module: contexts/crm/infrastructure/django_relationship_anomaly_notification_repository.py
Context: CRM.
Role: persist one anomaly notification per Contact silence period (INV-CRM-06).
"""

from ..domain.i_relationship_anomaly_notification_repository import (
    IRelationshipAnomalyNotificationRepository,
)
from ..domain.relationship_anomaly_notification import RelationshipAnomalyNotification
from .models import RelationshipAnomalyNotificationRecord


class DjangoRelationshipAnomalyNotificationRepository(
    IRelationshipAnomalyNotificationRepository
):
    """Persist CRM anomaly notifications with a database uniqueness guarantee."""

    def save_if_absent(self, notification: RelationshipAnomalyNotification) -> bool:
        """Create the notification only if this Contact silence period is unrecorded."""
        _, created = RelationshipAnomalyNotificationRecord.objects.get_or_create(
            contact_id=notification.contact_id,
            last_purchase_order_id=notification.last_purchase_order_id,
            defaults={
                "merchant_id": notification.merchant_id,
                "days_since_last_purchase": notification.days_since_last_purchase,
                "usual_interval_days": notification.usual_interval_days,
                "notified_at": notification.notified_at,
            },
        )
        return created
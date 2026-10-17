from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.repositories.i_relationship_anomaly_notification_repository import (
    IRelationshipAnomalyNotificationRepository,
)
from ...domain.services.relationship_anomaly_detector import RelationshipAnomalyDetector
from ...domain.entities.relationship_anomaly_notification import RelationshipAnomalyNotification
from ...domain.events.crm_events import RelationshipAnomalyDetected
from ..ports import (
    ICRMClock,
    ICRMOutbox,
    ICRMUnitOfWork,
    IRelationshipAnomalyConfiguration,
)


@dataclass(frozen=True)
class ContactAnomaly:
    """Documented summary of one anomalous CRM contact (INV-CRM-05)."""

    contact_id: UUID
    days_since_last_purchase: Decimal
    usual_interval_days: Decimal


@dataclass(frozen=True)
class DetectRelationshipAnomalyResult:
    """All newly emitted contact anomalies for one scheduled merchant run."""

    anomalies_detected: tuple[ContactAnomaly, ...]


class DetectRelationshipAnomalyUseCase:
    """Detect unusual purchase silence and atomically record each new alert.

    Trigger: scheduled CRM job; contract: docs/15-use-cases-catalog.md#contexte-crm.
    The pure detector uses CRM-owned purchase dates and the merchant's configured
    policy. Notification and `RelationshipAnomalyDetected` Outbox event are committed
    together, with a unique silence-period key preventing duplicate alerts.

    Args:
        contact_repository: CRM-owned Contact read/lock port; no Order Detection access.
        configuration: provider for configured default and merchant policy values.
        notification_repository: unique notification ledger for silence periods.
        outbox: CRM Outbox port sharing the UnitOfWork transaction.
        unit_of_work: CRM transaction boundary for notification and event persistence.
        clock: timezone-aware clock for deterministic inactivity calculations.

    Returns:
        Newly detected anomaly summaries; already-notified silence periods are omitted.

    Raises:
        InvalidRelationshipAnomalyPolicyException: if configured policy values are invalid.

    Protects INV-CRM-05, INV-CRM-06, INV-TR-02, and INV-TR-04.
    """

    def __init__(
        self,
        contact_repository: IContactRepository,
        configuration: IRelationshipAnomalyConfiguration,
        notification_repository: IRelationshipAnomalyNotificationRepository,
        outbox: ICRMOutbox,
        unit_of_work: ICRMUnitOfWork,
        clock: ICRMClock,
    ) -> None:
        """Inject CRM-owned repositories, policy, transaction, Outbox, and clock."""
        self._contact_repository = contact_repository
        self._configuration = configuration
        self._notification_repository = notification_repository
        self._outbox = outbox
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._detector = RelationshipAnomalyDetector()

    def execute(self, merchant_id: UUID) -> DetectRelationshipAnomalyResult:
        """Evaluate current CRM purchase histories and emit each new silence alert."""
        policy = self._configuration.for_merchant(merchant_id)
        contacts = self._contact_repository.find_by_merchant(merchant_id)
        anomalies: list[ContactAnomaly] = []

        for listed_contact in contacts:
            with self._unit_of_work:
                contact = self._contact_repository.find_for_update_by_id(listed_contact.id)
                if contact is None or contact.merchant_id != merchant_id:
                    continue

                now = self._clock.now_utc()
                detected = self._detector.detect(contact.purchase_history, now, policy)
                if detected is None:
                    continue

                last_purchase_order_id = max(
                    contact.purchase_history,
                    key=lambda entry: (entry.purchased_at, str(entry.order_id)),
                ).order_id
                notification = RelationshipAnomalyNotification(
                    merchant_id=merchant_id,
                    contact_id=contact.id,
                    last_purchase_order_id=last_purchase_order_id,
                    days_since_last_purchase=float(detected.days_since_last_purchase),
                    usual_interval_days=float(detected.usual_interval_days),
                    notified_at=now,
                )
                if not self._notification_repository.save_if_absent(notification):
                    continue

                self._outbox.add(
                    RelationshipAnomalyDetected(
                        merchant_id=merchant_id,
                        contact_id=contact.id,
                        last_purchase_order_id=last_purchase_order_id,
                        days_since_last_purchase=float(detected.days_since_last_purchase),
                        usual_interval_days=float(detected.usual_interval_days),
                        occurred_at=now,
                    )
                )
                anomalies.append(
                    ContactAnomaly(
                        contact_id=contact.id,
                        days_since_last_purchase=detected.days_since_last_purchase,
                        usual_interval_days=detected.usual_interval_days,
                    )
                )

        return DetectRelationshipAnomalyResult(anomalies_detected=tuple(anomalies))
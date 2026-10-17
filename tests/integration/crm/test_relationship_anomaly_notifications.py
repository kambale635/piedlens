from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import TransactionTestCase, override_settings

from contexts.crm.application.use_cases.detect_relationship_anomaly_use_case import (
    DetectRelationshipAnomalyUseCase,
)
from contexts.crm.domain.events.crm_events import RelationshipAnomalyDetected
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.domain.entities.relationship_anomaly_notification import (
    RelationshipAnomalyNotification,
)
from contexts.crm.domain.value_objects.relationship_anomaly_policy import RelationshipAnomalyPolicy
from contexts.crm.infrastructure.persistence.django_contact_repository import DjangoContactRepository
from contexts.crm.infrastructure.adapters.django_relationship_anomaly_configuration import (
    DjangoRelationshipAnomalyConfiguration,
)
from contexts.crm.infrastructure.messaging.django_crm_outbox import DjangoCRMOutbox
from contexts.crm.infrastructure.persistence.django_relationship_anomaly_notification_repository import (
    DjangoRelationshipAnomalyNotificationRepository,
)
from contexts.crm.infrastructure.persistence.django_unit_of_work import DjangoCRMUnitOfWork
from contexts.crm.infrastructure.persistence.models import (
    ContactRecord,
    OutboxEventRecord,
    RelationshipAnomalyNotificationRecord,
)
from shared_kernel.value_objects.money import Money


class FixedAnomalyConfiguration:
    def for_merchant(self, merchant_id):
        return RelationshipAnomalyPolicy(
            min_purchases=3,
            anomaly_multiplier="2.0",
            min_inactivity_days=7,
        )


class FixedClock:
    def __init__(self, now):
        self.now = now

    def now_utc(self):
        return self.now


class RelationshipAnomalyNotificationIntegrationTests(TransactionTestCase):
    """Verify one notification and event per silence period in one CRM transaction."""

    def setUp(self):
        self.unit_of_work = DjangoCRMUnitOfWork()
        self.notifications = DjangoRelationshipAnomalyNotificationRepository()
        self.outbox = DjangoCRMOutbox()
        self.merchant_id = uuid4()
        self.contact_id = uuid4()

    @override_settings(
        CRM_ANOMALY_MIN_PURCHASES=4,
        CRM_ANOMALY_MULTIPLIER="2.5",
        CRM_ANOMALY_MIN_INACTIVITY_DAYS=9,
        CRM_RELATIONSHIP_ANOMALY_BY_MERCHANT={},
    )
    def test_configuration_reads_thresholds_from_settings(self):
        policy = DjangoRelationshipAnomalyConfiguration().for_merchant(self.merchant_id)

        self.assertEqual(policy.min_purchases, 4)
        self.assertEqual(policy.anomaly_multiplier, 2.5)
        self.assertEqual(policy.min_inactivity_days, 9)

    @override_settings(
        CRM_ANOMALY_MIN_PURCHASES=3,
        CRM_ANOMALY_MULTIPLIER="2.0",
        CRM_ANOMALY_MIN_INACTIVITY_DAYS=7,
        CRM_RELATIONSHIP_ANOMALY_BY_MERCHANT={},
    )
    def test_configuration_applies_merchant_override(self):
        with self.settings(
            CRM_RELATIONSHIP_ANOMALY_BY_MERCHANT={
                str(self.merchant_id): {
                    "min_purchases": 5,
                    "anomaly_multiplier": "3.0",
                    "min_inactivity_days": 12,
                }
            }
        ):
            policy = DjangoRelationshipAnomalyConfiguration().for_merchant(
                self.merchant_id
            )

        self.assertEqual(policy.min_purchases, 5)
        self.assertEqual(policy.anomaly_multiplier, 3.0)
        self.assertEqual(policy.min_inactivity_days, 12)

    def record_notification(self, last_purchase_order_id, detected_at):
        notification = RelationshipAnomalyNotification(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            last_purchase_order_id=last_purchase_order_id,
            days_since_last_purchase=20,
            usual_interval_days=8,
            notified_at=detected_at,
        )
        event = RelationshipAnomalyDetected(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            last_purchase_order_id=last_purchase_order_id,
            days_since_last_purchase=20,
            usual_interval_days=8,
            occurred_at=detected_at,
        )
        with self.unit_of_work:
            created = self.notifications.save_if_absent(notification)
            if created:
                self.outbox.add(event)
        return created

    def test_one_notification_per_silence_period_and_new_period_after_purchase(self):
        first_last_order_id = uuid4()
        now = datetime.now(timezone.utc)

        self.assertTrue(self.record_notification(first_last_order_id, now))
        self.assertFalse(self.record_notification(first_last_order_id, now))
        self.assertTrue(
            self.record_notification(uuid4(), datetime.now(timezone.utc))
        )

        self.assertEqual(RelationshipAnomalyNotificationRecord.objects.count(), 2)
        self.assertEqual(OutboxEventRecord.objects.count(), 2)

    def test_notification_and_outbox_roll_back_together(self):
        notification = RelationshipAnomalyNotification(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            last_purchase_order_id=uuid4(),
            days_since_last_purchase=20,
            usual_interval_days=8,
            notified_at=datetime.now(timezone.utc),
        )
        event = RelationshipAnomalyDetected(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            last_purchase_order_id=notification.last_purchase_order_id,
            days_since_last_purchase=notification.days_since_last_purchase,
            usual_interval_days=notification.usual_interval_days,
            occurred_at=notification.notified_at,
        )

        with self.assertRaisesRegex(RuntimeError, "force rollback"):
            with self.unit_of_work:
                self.notifications.save_if_absent(notification)
                self.outbox.add(event)
                raise RuntimeError("force rollback")

        self.assertFalse(RelationshipAnomalyNotificationRecord.objects.exists())
        self.assertFalse(OutboxEventRecord.objects.exists())

    def test_detection_use_case_writes_alert_and_outbox_once_per_purchase_period(self):
        history_anchor = datetime(2026, 9, 28, tzinfo=timezone.utc)
        contact = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            external_identifier="anomaly-contact",
            display_name="Customer",
            initial_total_spent=Money("0", "XOF"),
            occurred_at=history_anchor,
        )
        purchase_ids = [uuid4() for _ in range(3)]
        for order_id, days_ago in zip(purchase_ids, (40, 30, 20)):
            contact.record_paid_order(
                order_id,
                Money("10", "XOF"),
                history_anchor - timedelta(days=days_ago),
            )

        contacts = DjangoContactRepository()
        with self.unit_of_work:
            contacts.get_or_create(contact)

        clock = FixedClock(datetime(2026, 9, 29, tzinfo=timezone.utc))
        use_case = DetectRelationshipAnomalyUseCase(
            contact_repository=contacts,
            configuration=FixedAnomalyConfiguration(),
            notification_repository=self.notifications,
            outbox=self.outbox,
            unit_of_work=self.unit_of_work,
            clock=clock,
        )

        first = use_case.execute(self.merchant_id)
        repeated = use_case.execute(self.merchant_id)

        self.assertEqual(len(first.anomalies_detected), 1)
        self.assertEqual(repeated.anomalies_detected, ())
        self.assertEqual(ContactRecord.objects.get(id=contact.id).order_count, 3)
        self.assertEqual(RelationshipAnomalyNotificationRecord.objects.count(), 1)
        self.assertEqual(OutboxEventRecord.objects.count(), 1)

        contact = contacts.find_for_update_by_id(contact.id)
        next_purchase_id = uuid4()
        contact.record_paid_order(next_purchase_id, Money("10", "XOF"), clock.now)
        with self.unit_of_work:
            contacts.save(contact)
        clock.now = datetime(2026, 10, 20, tzinfo=timezone.utc)

        next_period = use_case.execute(self.merchant_id)

        self.assertEqual(len(next_period.anomalies_detected), 1)
        self.assertEqual(RelationshipAnomalyNotificationRecord.objects.count(), 2)
        self.assertEqual(OutboxEventRecord.objects.count(), 2)


if __name__ == "__main__":
    import unittest

    unittest.main()

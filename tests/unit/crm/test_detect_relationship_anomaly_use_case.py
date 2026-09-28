import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from contexts.crm.application.detect_relationship_anomaly_use_case import (
    DetectRelationshipAnomalyUseCase,
)
from contexts.crm.domain.contact import Contact
from contexts.crm.domain.exceptions import InvalidRelationshipAnomalyPolicyException
from contexts.crm.domain.relationship_anomaly_policy import RelationshipAnomalyPolicy
from shared_kernel.value_objects.money import Money


class InMemoryContactRepository:
    def __init__(self, contacts):
        self.contacts = contacts

    def find_by_merchant(self, merchant_id):
        return [contact for contact in self.contacts if contact.merchant_id == merchant_id]

    def find_for_update_by_id(self, contact_id):
        return next((contact for contact in self.contacts if contact.id == contact_id), None)


class InMemoryNotificationRepository:
    def __init__(self):
        self.keys = set()

    def save_if_absent(self, notification):
        key = (notification.contact_id, notification.last_purchase_order_id)
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class InMemoryUnitOfWork:
    def __init__(self):
        self.entries = 0

    def __enter__(self):
        self.entries += 1
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class FixedConfiguration:
    def __init__(self, policy):
        self.policy = policy

    def for_merchant(self, merchant_id):
        return self.policy


class FixedClock:
    def __init__(self, now):
        self.now = now

    def now_utc(self):
        return self.now


class DetectRelationshipAnomalyUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.now = datetime(2026, 9, 28, tzinfo=timezone.utc)
        self.policy = RelationshipAnomalyPolicy(
            min_purchases=3,
            anomaly_multiplier=Decimal("2.0"),
            min_inactivity_days=7,
        )
        self.notifications = InMemoryNotificationRepository()
        self.outbox = InMemoryOutbox()
        self.unit_of_work = InMemoryUnitOfWork()

    def contact_with_purchase_days(self, days_ago):
        contact = Contact.create(
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            external_identifier=str(uuid4()),
            display_name="Customer",
            initial_total_spent=Money("0", "XOF"),
            occurred_at=self.now - timedelta(days=days_ago[0]),
        )
        for index, days in enumerate(days_ago):
            contact.record_paid_order(
                order_id=uuid4(),
                order_amount=Money("10", "XOF"),
                purchased_at=self.now - timedelta(days=days),
            )
        return contact

    def build_use_case(self, contacts):
        self.use_case = DetectRelationshipAnomalyUseCase(
            contact_repository=InMemoryContactRepository(contacts),
            configuration=FixedConfiguration(self.policy),
            notification_repository=self.notifications,
            outbox=self.outbox,
            unit_of_work=self.unit_of_work,
            clock=FixedClock(self.now),
        )

    def test_ignores_contacts_with_insufficient_purchase_history(self):
        contact = self.contact_with_purchase_days([60, 30])
        self.build_use_case([contact])

        result = self.use_case.execute(self.merchant_id)

        self.assertEqual(result.anomalies_detected, ())
        self.assertEqual(self.outbox.events, [])

    def test_uses_multiplier_and_inactivity_floor(self):
        contact = self.contact_with_purchase_days([40, 30, 20])
        self.build_use_case([contact])

        below_multiplier = self.use_case.execute(self.merchant_id)
        self.assertEqual(below_multiplier.anomalies_detected, ())

        self.now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        self.use_case._clock.now = self.now
        anomaly = self.use_case.execute(self.merchant_id)

        self.assertEqual(len(anomaly.anomalies_detected), 1)
        self.assertGreater(anomaly.anomalies_detected[0].days_since_last_purchase, 20)
        self.assertEqual(len(self.outbox.events), 1)

    def test_minimum_inactivity_floor_prevents_noisy_alerts(self):
        contact = self.contact_with_purchase_days([2, 1, 0])
        self.build_use_case([contact])
        self.now = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.use_case._clock.now = self.now

        result = self.use_case.execute(self.merchant_id)

        self.assertEqual(result.anomalies_detected, ())
        self.assertEqual(self.outbox.events, [])

    def test_same_silence_is_not_notified_twice_but_new_purchase_allows_new_alert(self):
        contact = self.contact_with_purchase_days([40, 30, 20])
        self.build_use_case([contact])
        self.now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        self.use_case._clock.now = self.now
        first = self.use_case.execute(self.merchant_id)
        repeated = self.use_case.execute(self.merchant_id)

        contact.record_paid_order(
            order_id=uuid4(),
            order_amount=Money("10", "XOF"),
            purchased_at=self.now,
        )
        self.now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        self.use_case._clock.now = self.now
        next_period = self.use_case.execute(self.merchant_id)

        self.assertEqual(len(first.anomalies_detected), 1)
        self.assertEqual(len(repeated.anomalies_detected), 0)
        self.assertEqual(len(next_period.anomalies_detected), 1)
        self.assertEqual(len(self.outbox.events), 2)

    def test_invalid_configured_policy_is_rejected(self):
        with self.assertRaises(InvalidRelationshipAnomalyPolicyException):
            RelationshipAnomalyPolicy(
                min_purchases=1,
                anomaly_multiplier=Decimal("0"),
                min_inactivity_days=-1,
            )


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.order_detection.application.ports.detection_configuration import (
    DetectionConfiguration,
)
from contexts.order_detection.application.use_cases.reconcile_order_status_from_message_use_case import (
    ReconcileOrderStatusFromMessageUseCase,
)
from contexts.order_detection.domain.entities.order import Order
from contexts.order_detection.domain.events.order_detection_events import OrderStatusChanged
from contexts.order_detection.domain.value_objects.order_status import OrderStatus
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrders:
    def __init__(self, orders):
        self.orders = list(orders)
        self.saved = []

    def find_orders_for_status_reconciliation(
        self, merchant_id, contact_id, expected_status, source_timestamp, within_days
    ):
        threshold = source_timestamp - timedelta(days=within_days)
        return [
            order
            for order in self.orders
            if order.merchant_id == merchant_id
            and order.contact_id == contact_id
            and order.status.value == expected_status
            and threshold <= order.created_at <= source_timestamp
        ]

    def save(self, order):
        self.saved.append(order)


class InMemoryProcessedEvents:
    def __init__(self):
        self.events = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.events

    def mark_processed(self, event_id, consumer_name):
        self.events.add((event_id, consumer_name))


class InMemoryUnitOfWork:
    def __init__(self):
        self.locked_contacts = []

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def lock_detection_contact(self, contact_id):
        self.locked_contacts.append(contact_id)


class FixedConfiguration:
    def for_merchant(self, merchant_id):
        return DetectionConfiguration(confidence_threshold=70, correlation_window_days=3)


class FixedIntentReader:
    def configured_intents(self, merchant_id):
        return frozenset({"payment_received", "delivery_confirmed"})


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class ReconcileOrderStatusFromMessageUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.contact_id = uuid4()
        self.source_time = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
        self.order = Order.detect(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            detected_amount=Money("15000", "XOF"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=self.source_time - timedelta(days=1),
        )
        self.orders = InMemoryOrders([self.order])
        self.processed = InMemoryProcessedEvents()
        self.unit_of_work = InMemoryUnitOfWork()
        self.outbox = InMemoryOutbox()
        self.use_case = ReconcileOrderStatusFromMessageUseCase(
            self.orders,
            self.processed,
            FixedConfiguration(),
            FixedIntentReader(),
            self.unit_of_work,
            self.outbox,
        )

    def execute(self, intent, event_id=None):
        return self.use_case.execute(
            event_id=event_id or uuid4(),
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            intent=intent,
            source_message_id=uuid4(),
            source_message_timestamp=self.source_time,
        )

    def test_payment_then_delivery_updates_latest_compatible_order_and_outbox(self):
        payment = self.execute("payment_received")
        delivery = self.execute("delivery_confirmed")

        self.assertEqual((payment.outcome, payment.status), ("updated", "paid_not_delivered"))
        self.assertEqual((delivery.outcome, delivery.status), ("updated", "paid_and_delivered"))
        self.assertEqual(self.order.status, OrderStatus.PAID_AND_DELIVERED)
        self.assertEqual(len(self.orders.saved), 2)
        self.assertEqual(len(self.outbox.events), 2)
        self.assertTrue(all(isinstance(event, OrderStatusChanged) for event in self.outbox.events))

    def test_unconfigured_intent_and_missing_compatible_order_are_ignored(self):
        unconfigured = self.execute("purchase")
        too_old = Order.detect(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            detected_amount=Money("1", "XOF"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=self.source_time - timedelta(days=4),
        )
        self.orders.orders = [too_old]
        missing = self.execute("payment_received")

        self.assertEqual(unconfigured.outcome, "ignored")
        self.assertEqual(missing.outcome, "ignored")
        self.assertEqual(self.orders.saved, [])
        self.assertEqual(self.outbox.events, [])

    def test_duplicate_event_is_already_processed_without_second_transition(self):
        event_id = uuid4()
        first = self.execute("payment_received", event_id)
        replay = self.execute("payment_received", event_id)

        self.assertEqual(first.outcome, "updated")
        self.assertEqual(replay.outcome, "already_processed")
        self.assertEqual(len(self.orders.saved), 1)
        self.assertEqual(len(self.outbox.events), 1)

    def test_payment_updates_only_the_newest_compatible_order(self):
        newest = Order.detect(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            detected_amount=Money("25000", "XOF"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=self.source_time - timedelta(hours=2),
        )
        oldest = self.order
        self.orders.orders = [oldest, newest]

        result = self.execute("payment_received")

        self.assertEqual(result.order_id, newest.id)
        self.assertEqual(oldest.status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(newest.status, OrderStatus.PAID_NOT_DELIVERED)


if __name__ == "__main__":
    unittest.main()
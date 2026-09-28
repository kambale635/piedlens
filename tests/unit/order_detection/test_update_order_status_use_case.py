import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.order_detection.application.events import OrderStatusChanged
from contexts.order_detection.application.update_order_status_use_case import (
    UpdateOrderStatusUseCase,
)
from contexts.order_detection.domain.exceptions import InvalidOrderTransitionException
from contexts.order_detection.domain.order import Order
from contexts.order_detection.domain.order_status import OrderStatus
from shared_kernel.application_exceptions import ResourceNotFoundException, ValidationException
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrderRepository:
    def __init__(self, order):
        self.order = order
        self.saved = []

    def find_by_id(self, order_id):
        return self.order if self.order and self.order.id == order_id else None

    def save(self, order):
        self.saved.append(order)

    def find_pending_by_contact(self, contact_id, within_days):
        return []

    def find_by_source_candidate_id(self, candidate_id):
        return None


class InMemoryUnitOfWork:
    def __init__(self):
        self.entered = False
        self.exited = False
        self.locked_order_ids = []

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.exited = True
        return False

    def lock_order(self, order_id):
        self.locked_order_ids.append(order_id)


class FixedClock:
    def __init__(self):
        self.instant = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)

    def now(self):
        return self.instant


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class UpdateOrderStatusUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.order = Order.detect(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("80.00", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
        )
        self.repository = InMemoryOrderRepository(self.order)
        self.unit_of_work = InMemoryUnitOfWork()
        self.outbox = InMemoryOutbox()
        self.clock = FixedClock()
        self.use_case = UpdateOrderStatusUseCase(
            order_repository=self.repository,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            clock=self.clock,
        )

    def test_valid_transition_persists_order_and_outbox_event(self):
        result = self.use_case.execute(
            order_id=self.order.id,
            new_status="paid_not_delivered",
            triggered_by="merchant",
        )

        self.assertEqual(result.status, "paid_not_delivered")
        self.assertEqual(result.updated_at, self.clock.instant)
        self.assertEqual(self.order.status, OrderStatus.PAID_NOT_DELIVERED)
        self.assertEqual(self.repository.saved, [self.order])
        self.assertEqual(len(self.outbox.events), 1)
        event = self.outbox.events[0]
        self.assertIsInstance(event, OrderStatusChanged)
        self.assertEqual(event.previous_status, "pending_payment")
        self.assertEqual(event.status, "paid_not_delivered")
        self.assertEqual(event.triggered_by, "merchant")
        self.assertEqual(self.unit_of_work.locked_order_ids, [self.order.id])

    def test_invalid_transition_is_rejected_by_aggregate_without_writes(self):
        self.order.change_status(OrderStatus.PAID_NOT_DELIVERED)
        self.order.change_status(OrderStatus.PAID_AND_DELIVERED)

        with self.assertRaises(InvalidOrderTransitionException):
            self.use_case.execute(
                order_id=self.order.id,
                new_status="pending_payment",
                triggered_by="system",
            )

        self.assertEqual(self.repository.saved, [])
        self.assertEqual(self.outbox.events, [])

    def test_missing_order_raises_not_found(self):
        self.repository.order = None

        with self.assertRaises(ResourceNotFoundException):
            self.use_case.execute(
                order_id=uuid4(),
                new_status="cancelled",
                triggered_by="system",
            )

        self.assertEqual(self.repository.saved, [])
        self.assertEqual(self.outbox.events, [])

    def test_invalid_actor_is_rejected_before_opening_transaction(self):
        with self.assertRaises(ValidationException):
            self.use_case.execute(
                order_id=self.order.id,
                new_status="paid_not_delivered",
                triggered_by="unknown",
            )

        self.assertFalse(self.unit_of_work.entered)


if __name__ == "__main__":
    unittest.main()
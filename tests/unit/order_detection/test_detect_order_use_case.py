import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.order_detection.application.detect_order_use_case import DetectOrderUseCase
from contexts.order_detection.application.detection_configuration import DetectionConfiguration
from contexts.order_detection.application.events import (
    DetectionCandidateCreated,
    OrderDetected,
)
from contexts.order_detection.application.evaluation_result import EvaluationResult
from contexts.order_detection.domain.detection_candidate import DetectionCandidate
from contexts.order_detection.domain.exceptions import (
    DetectionCandidateAlreadyReviewedException,
    InvalidOrderTransitionException,
)
from contexts.order_detection.domain.order import Order
from contexts.order_detection.domain.order_status import OrderStatus
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrderRepository:
    def __init__(self, orders=None):
        self.orders = list(orders or [])
        self.saved = []
        self.last_window_days = None

    def save(self, order):
        self.saved.append(order)

    def find_pending_by_contact(self, contact_id, within_days):
        self.last_window_days = within_days
        return [order for order in self.orders if order.contact_id == contact_id]


class InMemoryCandidateRepository:
    def __init__(self):
        self.saved = []

    def save(self, candidate):
        self.saved.append(candidate)


class FixedConfiguration:
    def for_merchant(self, merchant_id):
        return DetectionConfiguration(confidence_threshold=70, correlation_window_days=3)


class InMemoryUnitOfWork:
    def __init__(self):
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.exited = True
        return False


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class OrderAggregateTests(unittest.TestCase):
    def test_rejects_invalid_transition_from_delivered_to_pending(self):
        order = Order.detect(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("25.00", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
        )
        order.change_status(OrderStatus.PAID_NOT_DELIVERED)
        order.change_status(OrderStatus.PAID_AND_DELIVERED)

        with self.assertRaises(InvalidOrderTransitionException):
            order.change_status(OrderStatus.PENDING_PAYMENT)

        with self.assertRaises(AttributeError):
            order.status = OrderStatus.PENDING_PAYMENT

    def test_candidate_cannot_be_decided_twice(self):
        candidate = DetectionCandidate.create(
            merchant_id=uuid4(),
            contact_id=uuid4(),
            detected_amount=Money("25.00", "USD"),
            confidence_score=ConfidenceScore(60),
            source_message_id=uuid4(),
        )
        candidate.reject()

        with self.assertRaises(DetectionCandidateAlreadyReviewedException):
            candidate.promote()
        with self.assertRaises(AttributeError):
            candidate.status = candidate.status.PENDING_REVIEW


class DetectOrderUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.contact_id = uuid4()
        self.source_message_id = uuid4()
        self.order_repository = InMemoryOrderRepository()
        self.candidate_repository = InMemoryCandidateRepository()
        self.unit_of_work = InMemoryUnitOfWork()
        self.outbox = InMemoryOutbox()
        self.use_case = DetectOrderUseCase(
            order_repository=self.order_repository,
            candidate_repository=self.candidate_repository,
            configuration=FixedConfiguration(),
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

    def execute(self, score, amount=None, intent="purchase", timestamp=None):
        return self.use_case.execute(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            evaluation_result=EvaluationResult(
                confidence_score=ConfidenceScore(score),
                intent=intent,
                amount=amount,
            ),
            source_message_id=self.source_message_id,
            source_message_timestamp=timestamp or datetime.now(timezone.utc),
        )

    def test_low_confidence_creates_candidate_without_order(self):
        result = self.execute(69, Money("125.00", "USD"))

        self.assertEqual(result.outcome, "candidate_created")
        self.assertEqual(len(self.candidate_repository.saved), 1)
        self.assertIsInstance(self.candidate_repository.saved[0], DetectionCandidate)
        self.assertEqual(self.order_repository.saved, [])
        self.assertIsInstance(self.outbox.events[0], DetectionCandidateCreated)
        self.assertTrue(self.unit_of_work.entered)
        self.assertTrue(self.unit_of_work.exited)

    def test_threshold_score_creates_order_and_outbox_event(self):
        result = self.execute(70, Money("125.00", "USD"))

        self.assertEqual(result.outcome, "order_created")
        self.assertEqual(result.status, "pending_payment")
        self.assertEqual(len(self.order_repository.saved), 1)
        self.assertIsInstance(self.outbox.events[0], OrderDetected)
        self.assertEqual(self.candidate_repository.saved, [])

    def test_does_not_replace_newer_amount_when_old_message_is_processed_late(self):
        newer_timestamp = datetime.now(timezone.utc)
        existing_order = Order.detect(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            detected_amount=Money("200.00", "USD"),
            confidence_score=ConfidenceScore(90),
            source_message_id=uuid4(),
            occurred_at=newer_timestamp,
        )
        self.order_repository.orders.append(existing_order)
        result = self.execute(
            80,
            Money("150.00", "USD"),
            timestamp=newer_timestamp - timedelta(minutes=5),
        )

        self.assertEqual(result.order_id, existing_order.id)
        self.assertEqual(existing_order.detected_amount, Money("200.00", "USD"))
        self.assertEqual(self.order_repository.last_window_days, 3)

    def test_replaces_amount_when_source_message_is_newer(self):
        older_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
        existing_order = Order.detect(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            detected_amount=Money("150.00", "USD"),
            confidence_score=ConfidenceScore(80),
            source_message_id=uuid4(),
            occurred_at=older_timestamp,
        )
        self.order_repository.orders.append(existing_order)

        self.execute(
            85,
            Money("200.00", "USD"),
            timestamp=older_timestamp + timedelta(minutes=5),
        )

        self.assertEqual(existing_order.detected_amount, Money("200.00", "USD"))

    def test_ignores_non_purchase_or_missing_amount(self):
        non_purchase = self.execute(95, Money("125.00", "USD"), intent="unknown")
        missing_amount = self.execute(95, amount=None)

        self.assertEqual(non_purchase.outcome, "ignored")
        self.assertEqual(missing_amount.outcome, "ignored")
        self.assertEqual(self.order_repository.saved, [])
        self.assertEqual(self.candidate_repository.saved, [])
        self.assertEqual(self.outbox.events, [])


if __name__ == "__main__":
    unittest.main()
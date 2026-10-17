import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.order_detection.application.use_cases.detect_order_use_case import DetectOrderUseCase
from contexts.order_detection.application.ports.detection_configuration import DetectionConfiguration
from contexts.order_detection.domain.events.order_detection_events import (
    DetectionCandidateCreated,
    OrderDetected,
)
from contexts.order_detection.application.dto.evaluation_result import EvaluationResult
from contexts.order_detection.domain.entities.detection_candidate import DetectionCandidate
from contexts.order_detection.domain.exceptions.order_detection_exceptions import (
    DetectionCandidateAlreadyReviewedException,
    InvalidOrderTransitionException,
)
from contexts.order_detection.domain.entities.order import Order
from contexts.order_detection.domain.value_objects.order_status import OrderStatus
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

    def find_for_update_by_id(self, order_id):
        return next((order for order in self.orders if order.id == order_id), None)


class InMemoryCandidateRepository:
    def __init__(self):
        self.saved = []

    def save(self, candidate):
        self.saved.append(candidate)


class InMemoryProcessedEvents:
    def __init__(self):
        self.processed = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.processed

    def mark_processed(self, event_id, consumer_name):
        self.processed.add((event_id, consumer_name))


class InMemoryContactRedirects:
    def __init__(self):
        self.redirects = {}

    def register(self, merchant_id, merged_contact_id, primary_contact_id):
        self.redirects[merged_contact_id] = (merchant_id, primary_contact_id)

    def resolve(self, merchant_id, contact_id):
        while contact_id in self.redirects:
            redirect_merchant_id, primary_contact_id = self.redirects[contact_id]
            if redirect_merchant_id != merchant_id:
                break
            contact_id = primary_contact_id
        return contact_id


class FixedConfiguration:
    def for_merchant(self, merchant_id):
        return DetectionConfiguration(confidence_threshold=70, correlation_window_days=3)


class InMemoryUnitOfWork:
    def __init__(self):
        self.entered = 0
        self.exited = 0
        self.locked_contacts = []

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.exited += 1
        return False

    def lock_detection_contact(self, contact_id):
        self.locked_contacts.append(contact_id)


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
        self.event_id = uuid4()
        self.source_message_id = uuid4()
        self.order_repository = InMemoryOrderRepository()
        self.candidate_repository = InMemoryCandidateRepository()
        self.unit_of_work = InMemoryUnitOfWork()
        self.outbox = InMemoryOutbox()
        self.processed_events = InMemoryProcessedEvents()
        self.contact_redirects = InMemoryContactRedirects()
        self.use_case = DetectOrderUseCase(
            order_repository=self.order_repository,
            candidate_repository=self.candidate_repository,
            configuration=FixedConfiguration(),
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            processed_events=self.processed_events,
            contact_redirects=self.contact_redirects,
        )

    def execute(
        self,
        score,
        amount=None,
        intent="purchase",
        timestamp=None,
        event_id=None,
    ):
        return self.use_case.execute(
            merchant_id=self.merchant_id,
            event_id=event_id or self.event_id,
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
        self.assertGreater(self.unit_of_work.entered, 0)
        self.assertEqual(self.unit_of_work.entered, self.unit_of_work.exited)
        self.assertIn(
            (self.event_id, self.use_case.CONSUMER_NAME),
            self.processed_events.processed,
        )

    def test_threshold_score_creates_order_and_outbox_event(self):
        result = self.execute(70, Money("125.00", "USD"))

        self.assertEqual(result.outcome, "order_created")
        self.assertEqual(result.status, "pending_payment")
        self.assertEqual(len(self.order_repository.saved), 1)
        self.assertIsInstance(self.outbox.events[0], OrderDetected)
        self.assertEqual(self.candidate_repository.saved, [])

    def test_same_event_redelivery_does_not_duplicate_order_or_candidate(self):
        candidate_result = self.execute(69, Money("125.00", "USD"))
        candidate_replay = self.execute(69, Money("125.00", "USD"))
        self.assertEqual(candidate_result.outcome, "candidate_created")
        self.assertEqual(candidate_replay.outcome, "already_processed")
        self.assertEqual(len(self.candidate_repository.saved), 1)

        self.event_id = uuid4()
        order_result = self.execute(90, Money("250.00", "USD"))
        order_replay = self.execute(90, Money("250.00", "USD"))
        self.assertEqual(order_result.outcome, "order_created")
        self.assertEqual(order_replay.outcome, "already_processed")
        self.assertEqual(len(self.order_repository.saved), 1)
        self.assertEqual(len(self.outbox.events), 2)

    def test_contact_detection_lock_is_taken_for_orders_and_candidates(self):
        self.execute(69, Money("125.00", "USD"))
        self.event_id = uuid4()
        self.execute(90, Money("250.00", "USD"))

        self.assertEqual(self.unit_of_work.locked_contacts, [self.contact_id, self.contact_id])

    def test_new_detection_uses_primary_contact_after_merge_redirect(self):
        primary_contact_id = uuid4()
        self.contact_redirects.register(
            self.merchant_id,
            self.contact_id,
            primary_contact_id,
        )

        self.execute(90, Money("250.00", "USD"))

        self.assertEqual(self.order_repository.saved[0].contact_id, primary_contact_id)
        self.assertIn(primary_contact_id, self.unit_of_work.locked_contacts)

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
        missing_amount = self.execute(95, amount=None, event_id=uuid4())

        self.assertEqual(non_purchase.outcome, "ignored")
        self.assertEqual(missing_amount.outcome, "ignored")
        self.assertEqual(self.order_repository.saved, [])
        self.assertEqual(self.candidate_repository.saved, [])
        self.assertEqual(self.outbox.events, [])


if __name__ == "__main__":
    unittest.main()
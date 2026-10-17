import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.order_detection.application.use_cases.create_order_from_promoted_detection_use_case import (
    CreateOrderFromPromotedDetectionUseCase,
)
from contexts.order_detection.domain.events.order_detection_events import (
    DetectionCandidatePromoted,
    OrderDetected,
)
from contexts.order_detection.domain.entities.order import Order
from contexts.order_detection.domain.value_objects.order_status import OrderStatus
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrderRepository:
    def __init__(self):
        self.orders = []
        self.saved = []

    def save(self, order):
        self.saved.append(order)
        self.orders.append(order)

    def find_by_source_candidate_id(self, candidate_id):
        return next(
            (order for order in self.orders if order.source_candidate_id == candidate_id),
            None,
        )

    def find_pending_by_contact(self, contact_id, within_days):
        return []


class InMemoryProcessedEventRepository:
    def __init__(self):
        self.processed = set()
        self.marked = []

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.processed

    def mark_processed(self, event_id, consumer_name):
        self.processed.add((event_id, consumer_name))
        self.marked.append((event_id, consumer_name))


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


class InMemoryUnitOfWork:
    def __init__(self):
        self.entered = 0
        self.exited = 0
        self.locked_candidate_ids = []
        self.locked_contact_ids = []

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.exited += 1
        return False

    def lock_candidate_creation(self, candidate_id):
        self.locked_candidate_ids.append(candidate_id)

    def lock_detection_contact(self, contact_id):
        self.locked_contact_ids.append(contact_id)


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class CreateOrderFromPromotedDetectionUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.candidate_id = uuid4()
        self.event = DetectionCandidatePromoted(
            candidate_id=self.candidate_id,
            merchant_id=uuid4(),
            contact_id=uuid4(),
            source_message_id=uuid4(),
            detected_amount=Money("249.50", "USD"),
            confidence_score=ConfidenceScore(65),
            matched_rule_ids=(uuid4(),),
            event_id=uuid4(),
            occurred_at=datetime.now(timezone.utc),
        )
        self.order_repository = InMemoryOrderRepository()
        self.processed_events = InMemoryProcessedEventRepository()
        self.contact_redirects = InMemoryContactRedirects()
        self.unit_of_work = InMemoryUnitOfWork()
        self.outbox = InMemoryOutbox()
        self.use_case = CreateOrderFromPromotedDetectionUseCase(
            order_repository=self.order_repository,
            processed_events=self.processed_events,
            contact_redirects=self.contact_redirects,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

    def test_creates_order_outbox_event_and_processed_marker(self):
        result = self.use_case.execute(self.event)

        self.assertTrue(result.created)
        order = self.order_repository.saved[0]
        self.assertIsInstance(order, Order)
        self.assertEqual(order.status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(order.source_candidate_id, self.candidate_id)
        self.assertIsInstance(self.outbox.events[0], OrderDetected)
        self.assertEqual(self.outbox.events[0].source_candidate_id, self.candidate_id)
        self.assertEqual(
            self.processed_events.marked,
            [(self.event.event_id, self.use_case.CONSUMER_NAME)],
        )
        self.assertEqual(self.unit_of_work.entered, self.unit_of_work.exited)
        self.assertEqual(self.unit_of_work.locked_candidate_ids, [self.candidate_id])

    def test_late_promotion_uses_primary_contact_after_merge_redirect(self):
        primary_contact_id = uuid4()
        self.contact_redirects.register(
            self.event.merchant_id,
            self.event.contact_id,
            primary_contact_id,
        )

        self.use_case.execute(self.event)

        self.assertEqual(self.order_repository.saved[0].contact_id, primary_contact_id)
        self.assertIn(primary_contact_id, self.unit_of_work.locked_contact_ids)

    def test_redelivery_of_same_event_does_not_duplicate_order_or_outbox(self):
        first_result = self.use_case.execute(self.event)
        second_result = self.use_case.execute(self.event)

        self.assertTrue(first_result.created)
        self.assertFalse(second_result.created)
        self.assertEqual(first_result.order_id, second_result.order_id)
        self.assertEqual(len(self.order_repository.saved), 1)
        self.assertEqual(len(self.outbox.events), 1)

    def test_new_event_id_for_same_candidate_still_does_not_duplicate_order(self):
        self.use_case.execute(self.event)
        duplicate_delivery = DetectionCandidatePromoted(
            candidate_id=self.event.candidate_id,
            merchant_id=self.event.merchant_id,
            contact_id=self.event.contact_id,
            source_message_id=self.event.source_message_id,
            detected_amount=self.event.detected_amount,
            confidence_score=self.event.confidence_score,
            matched_rule_ids=self.event.matched_rule_ids,
            event_id=uuid4(),
            occurred_at=self.event.occurred_at,
        )

        result = self.use_case.execute(duplicate_delivery)

        self.assertFalse(result.created)
        self.assertEqual(len(self.order_repository.saved), 1)
        self.assertEqual(len(self.outbox.events), 1)
        self.assertIn(
            (duplicate_delivery.event_id, self.use_case.CONSUMER_NAME),
            self.processed_events.processed,
        )


if __name__ == "__main__":
    unittest.main()
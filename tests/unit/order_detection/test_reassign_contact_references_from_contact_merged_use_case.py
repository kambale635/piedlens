import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.order_detection.domain.events.order_detection_events import ContactMerged
from contexts.order_detection.application.use_cases.reassign_contact_references_from_contact_merged_use_case import (
    ReassignContactReferencesFromContactMergedUseCase,
)
from contexts.order_detection.domain.entities.detection_candidate import DetectionCandidate
from contexts.order_detection.domain.entities.detection_candidate import DetectionCandidateStatus
from contexts.order_detection.domain.entities.order import Order
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryOrderRepository:
    def __init__(self, orders):
        self.orders = {order.id: order for order in orders}
        self.saved = []

    def find_ids_by_contact(self, contact_id):
        return [order.id for order in self.orders.values() if order.contact_id == contact_id]

    def find_for_update_by_id(self, order_id):
        return self.orders.get(order_id)

    def save(self, order):
        self.orders[order.id] = order
        self.saved.append(order.id)


class InMemoryCandidateRepository:
    def __init__(self, candidates):
        self.candidates = {candidate.id: candidate for candidate in candidates}
        self.saved = []
        self.fail_on_listing = False

    def find_ids_by_contact(self, contact_id):
        if self.fail_on_listing:
            self.fail_on_listing = False
            raise RuntimeError("temporary candidate scan failure")
        return [
            candidate.id
            for candidate in self.candidates.values()
            if candidate.contact_id == contact_id
        ]

    def find_for_update_by_id(self, candidate_id):
        return self.candidates.get(candidate_id)

    def save(self, candidate):
        self.candidates[candidate.id] = candidate
        self.saved.append(candidate.id)


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


class InMemoryUnitOfWork:
    def __init__(self):
        self.entered = 0
        self.active = 0
        self.maximum_active = 0
        self.locked_contact_ids = []

    def __enter__(self):
        self.entered += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.active -= 1
        return False

    def lock_detection_contact(self, contact_id):
        self.locked_contact_ids.append(contact_id)


class ReassignContactReferencesFromContactMergedUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.merged_contact_id = uuid4()
        self.primary_contact_id = uuid4()
        self.other_contact_id = uuid4()
        occurred_at = datetime(2026, 9, 20, tzinfo=timezone.utc)
        self.orders = [
            Order.detect(
                merchant_id=self.merchant_id,
                contact_id=self.merged_contact_id,
                detected_amount=Money("10", "XOF"),
                confidence_score=ConfidenceScore(80),
                source_message_id=uuid4(),
                occurred_at=occurred_at,
            )
            for _ in range(2)
        ]
        self.unrelated_order = Order.detect(
            merchant_id=self.merchant_id,
            contact_id=self.other_contact_id,
            detected_amount=Money("12", "XOF"),
            confidence_score=ConfidenceScore(80),
            source_message_id=uuid4(),
            occurred_at=occurred_at,
        )
        self.candidates = [
            DetectionCandidate.create(
                merchant_id=self.merchant_id,
                contact_id=self.merged_contact_id,
                detected_amount=Money("20", "USD"),
                confidence_score=ConfidenceScore(60),
                source_message_id=uuid4(),
                occurred_at=occurred_at,
            ),
            DetectionCandidate.create(
                merchant_id=self.merchant_id,
                contact_id=self.merged_contact_id,
                detected_amount=Money("30", "USD"),
                confidence_score=ConfidenceScore(55),
                source_message_id=uuid4(),
                occurred_at=occurred_at,
            ),
        ]
        self.candidates[1].reject()
        self.unrelated_candidate = DetectionCandidate.create(
            merchant_id=self.merchant_id,
            contact_id=self.other_contact_id,
            detected_amount=Money("40", "USD"),
            confidence_score=ConfidenceScore(50),
            source_message_id=uuid4(),
            occurred_at=occurred_at,
        )
        self.order_repository = InMemoryOrderRepository(
            [*self.orders, self.unrelated_order]
        )
        self.candidate_repository = InMemoryCandidateRepository(
            [*self.candidates, self.unrelated_candidate]
        )
        self.processed_events = InMemoryProcessedEvents()
        self.redirects = InMemoryContactRedirects()
        self.unit_of_work = InMemoryUnitOfWork()
        self.event = ContactMerged(
            event_id=uuid4(),
            merchant_id=self.merchant_id,
            primary_contact_id=self.primary_contact_id,
            merged_contact_id=self.merged_contact_id,
        )
        self.use_case = self.create_use_case()

    def create_use_case(self):
        return ReassignContactReferencesFromContactMergedUseCase(
            order_repository=self.order_repository,
            candidate_repository=self.candidate_repository,
            processed_events=self.processed_events,
            redirects=self.redirects,
            unit_of_work=self.unit_of_work,
        )

    def test_reassigns_only_matching_aggregates_and_redelivery_is_noop(self):
        result = self.use_case.execute(self.event)
        replay = self.use_case.execute(self.event)

        self.assertEqual(result.reassigned_order_count, 2)
        self.assertEqual(result.reassigned_candidate_count, 2)
        self.assertEqual((replay.reassigned_order_count, replay.reassigned_candidate_count), (0, 0))
        self.assertTrue(
            all(order.contact_id == self.primary_contact_id for order in self.orders)
        )
        self.assertEqual(self.unrelated_order.contact_id, self.other_contact_id)
        self.assertTrue(
            all(
                candidate.contact_id == self.primary_contact_id
                for candidate in self.candidates
            )
        )
        self.assertEqual(self.candidates[1].status, DetectionCandidateStatus.REJECTED)
        self.assertEqual(self.unrelated_candidate.contact_id, self.other_contact_id)
        self.assertEqual(len(self.order_repository.saved), 2)
        self.assertEqual(len(self.candidate_repository.saved), 2)
        self.assertIn((self.event.event_id, self.use_case.CONSUMER_NAME), self.processed_events.processed)
        self.assertEqual(
            self.redirects.resolve(self.merchant_id, self.merged_contact_id),
            self.primary_contact_id,
        )
        self.assertEqual(self.unit_of_work.active, 0)
        self.assertEqual(self.unit_of_work.maximum_active, 1)

    def test_retry_resumes_after_order_transactions_commit_but_candidate_scan_fails(self):
        self.candidate_repository.fail_on_listing = True

        with self.assertRaisesRegex(RuntimeError, "temporary candidate scan failure"):
            self.use_case.execute(self.event)

        self.assertTrue(
            all(order.contact_id == self.primary_contact_id for order in self.orders)
        )
        self.assertTrue(
            all(candidate.contact_id == self.merged_contact_id for candidate in self.candidates)
        )
        self.assertNotIn(
            (self.event.event_id, self.use_case.CONSUMER_NAME),
            self.processed_events.processed,
        )

        result = self.use_case.execute(self.event)

        self.assertEqual(result.reassigned_order_count, 0)
        self.assertEqual(result.reassigned_candidate_count, 2)
        self.assertTrue(
            all(candidate.contact_id == self.primary_contact_id for candidate in self.candidates)
        )
        self.assertIn((self.event.event_id, self.use_case.CONSUMER_NAME), self.processed_events.processed)


if __name__ == "__main__":
    unittest.main()
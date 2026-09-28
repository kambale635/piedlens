import unittest
from uuid import uuid4

from contexts.order_detection.application.events import (
    DetectionCandidatePromoted,
    DetectionCandidateRejected,
    DetectionCorrectedByMerchant,
)
from contexts.order_detection.application.validate_or_reject_detection_use_case import (
    ValidateOrRejectDetectionUseCase,
)
from contexts.order_detection.domain.detection_candidate import (
    DetectionCandidate,
    DetectionCandidateStatus,
)
from contexts.order_detection.domain.exceptions import (
    DetectionCandidateAlreadyReviewedException,
)
from shared_kernel.application_exceptions import (
    ResourceNotFoundException,
    ValidationException,
)
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryCandidateRepository:
    def __init__(self, candidate):
        self.candidate = candidate
        self.saved = []

    def find_by_id(self, candidate_id):
        return self.candidate if self.candidate.id == candidate_id else None

    def save(self, candidate):
        self.saved.append(candidate)


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


class ValidateOrRejectDetectionUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.contact_id = uuid4()
        self.rule_ids = (uuid4(), uuid4())
        self.candidate = DetectionCandidate.create(
            merchant_id=self.merchant_id,
            contact_id=self.contact_id,
            detected_amount=Money("180.00", "USD"),
            confidence_score=ConfidenceScore(62),
            source_message_id=uuid4(),
            matched_rule_ids=self.rule_ids,
        )
        self.repository = InMemoryCandidateRepository(self.candidate)
        self.unit_of_work = InMemoryUnitOfWork()
        self.outbox = InMemoryOutbox()
        self.use_case = ValidateOrRejectDetectionUseCase(
            candidate_repository=self.repository,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

    def test_validation_promotes_candidate_and_emits_events_without_creating_order(self):
        result = self.use_case.execute(
            candidate_id=self.candidate.id,
            decision="validate",
            merchant_id=self.merchant_id,
        )

        self.assertEqual(result.status, "promoted")
        self.assertEqual(self.candidate.status, DetectionCandidateStatus.PROMOTED)
        self.assertEqual(self.repository.saved, [self.candidate])
        self.assertIsInstance(self.outbox.events[0], DetectionCandidatePromoted)
        corrections = self.outbox.events[1:]
        self.assertTrue(all(isinstance(event, DetectionCorrectedByMerchant) for event in corrections))
        self.assertEqual({event.rule_id for event in corrections}, set(self.rule_ids))
        self.assertTrue(all(event.was_correct for event in corrections))
        self.assertTrue(self.unit_of_work.entered)
        self.assertTrue(self.unit_of_work.exited)

    def test_rejection_emits_rejected_event_and_negative_feedback(self):
        result = self.use_case.execute(
            candidate_id=self.candidate.id,
            decision="reject",
            merchant_id=self.merchant_id,
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(self.candidate.status, DetectionCandidateStatus.REJECTED)
        self.assertIsInstance(self.outbox.events[0], DetectionCandidateRejected)
        corrections = self.outbox.events[1:]
        self.assertTrue(all(isinstance(event, DetectionCorrectedByMerchant) for event in corrections))
        self.assertTrue(all(not event.was_correct for event in corrections))

    def test_candidate_from_another_merchant_is_not_accessible(self):
        with self.assertRaises(ResourceNotFoundException):
            self.use_case.execute(
                candidate_id=self.candidate.id,
                decision="validate",
                merchant_id=uuid4(),
            )

        self.assertEqual(self.repository.saved, [])
        self.assertEqual(self.outbox.events, [])

    def test_terminal_candidate_cannot_be_reviewed_twice(self):
        self.candidate.reject()

        with self.assertRaises(DetectionCandidateAlreadyReviewedException):
            self.use_case.execute(
                candidate_id=self.candidate.id,
                decision="validate",
                merchant_id=self.merchant_id,
            )

        self.assertEqual(self.outbox.events, [])

    def test_invalid_decision_is_rejected_before_transaction(self):
        with self.assertRaises(ValidationException):
            self.use_case.execute(
                candidate_id=self.candidate.id,
                decision="approve",
                merchant_id=self.merchant_id,
            )

        self.assertFalse(self.unit_of_work.entered)
        self.assertEqual(self.outbox.events, [])


if __name__ == "__main__":
    unittest.main()
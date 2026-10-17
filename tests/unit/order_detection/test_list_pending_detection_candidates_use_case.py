import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.order_detection.application.use_cases.list_pending_detection_candidates_use_case import (
    ListPendingDetectionCandidatesUseCase,
)
from contexts.order_detection.domain.entities.detection_candidate import DetectionCandidate
from contexts.order_detection.domain.exceptions.order_detection_exceptions import DetectionCandidateAlreadyReviewedException
from shared_kernel.application_exceptions import ValidationException
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


class InMemoryCandidateRepository:
    def __init__(self, candidates):
        self.candidates = candidates
        self.request = None

    def save(self, candidate):
        pass

    def find_by_id(self, candidate_id):
        return next((candidate for candidate in self.candidates if candidate.id == candidate_id), None)

    def find_pending_by_merchant(self, merchant_id, offset, limit):
        self.request = (merchant_id, offset, limit)
        pending = [
            candidate
            for candidate in self.candidates
            if candidate.merchant_id == merchant_id
            and candidate.status.value == "pending_review"
        ]
        pending.sort(key=lambda candidate: (candidate.created_at, candidate.id))
        return pending[offset : offset + limit], len(pending)


def make_candidate(merchant_id, created_at, status=None):
    candidate = DetectionCandidate.create(
        merchant_id=merchant_id,
        contact_id=uuid4(),
        detected_amount=Money("25.00", "USD"),
        confidence_score=ConfidenceScore(60),
        source_message_id=uuid4(),
        occurred_at=created_at,
    )
    if status == "rejected":
        candidate.reject()
    if status == "promoted":
        candidate.promote()
    return candidate


class ListPendingDetectionCandidatesUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        base_time = datetime(2026, 9, 20, tzinfo=timezone.utc)
        self.candidates = [
            make_candidate(self.merchant_id, base_time + timedelta(hours=index))
            for index in range(3)
        ]
        self.candidates.append(make_candidate(self.merchant_id, base_time, "rejected"))
        self.candidates.append(make_candidate(uuid4(), base_time))
        self.repository = InMemoryCandidateRepository(self.candidates)
        self.use_case = ListPendingDetectionCandidatesUseCase(self.repository)

    def test_returns_stable_page_and_merchant_scoped_total(self):
        result = self.use_case.execute(self.merchant_id, page=2, page_size=2)

        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].candidate_id, self.candidates[2].id)
        self.assertEqual(self.repository.request, (self.merchant_id, 2, 2))

    def test_uses_documented_pagination_defaults(self):
        self.use_case.execute(self.merchant_id)

        self.assertEqual(self.repository.request, (self.merchant_id, 0, 50))

    def test_rejects_invalid_page_and_page_size(self):
        invalid_pairs = [
            (0, 50),
            (-1, 50),
            (1.2, 50),
            (True, 50),
            (1, 0),
            (1, -1),
            (1, 101),
            (1, False),
        ]
        for page, page_size in invalid_pairs:
            with self.subTest(page=page, page_size=page_size):
                with self.assertRaises(ValidationException):
                    self.use_case.execute(self.merchant_id, page, page_size)

        self.assertIsNone(self.repository.request)


if __name__ == "__main__":
    unittest.main()
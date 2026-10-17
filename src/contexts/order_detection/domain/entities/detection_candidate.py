from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money

from ..exceptions.order_detection_exceptions import DetectionCandidateAlreadyReviewedException


class DetectionCandidateStatus(StrEnum):
    """Manual-review lifecycle for low-confidence detections (INV-OD-07)."""

    PENDING_REVIEW = "pending_review"
    PROMOTED = "promoted"
    REJECTED = "rejected"


@dataclass
class DetectionCandidate:
    """Stores a low-confidence detection without creating an Order (INV-OD-04/07).

    A candidate can be decided once. Promotion links a separately identified Order;
    rejection never creates one. See docs/02-domain-model.md.
    """

    id: UUID
    merchant_id: UUID
    contact_id: UUID
    detected_amount: Money
    confidence_score: ConfidenceScore
    source_message_id: UUID
    matched_rule_ids: tuple[UUID, ...]
    _status: DetectionCandidateStatus
    created_at: datetime

    @classmethod
    def create(
        cls,
        merchant_id: UUID,
        contact_id: UUID,
        detected_amount: Money,
        confidence_score: ConfidenceScore,
        source_message_id: UUID,
        matched_rule_ids: tuple[UUID, ...] = (),
        occurred_at: datetime | None = None,
    ) -> "DetectionCandidate":
        """Create a pending-review candidate without an Order aggregate."""
        return cls(
            id=uuid4(),
            merchant_id=merchant_id,
            contact_id=contact_id,
            detected_amount=detected_amount,
            confidence_score=confidence_score,
            source_message_id=source_message_id,
            matched_rule_ids=matched_rule_ids,
            _status=DetectionCandidateStatus.PENDING_REVIEW,
            created_at=occurred_at or datetime.now(timezone.utc),
        )

    def promote(self) -> None:
        """Record one explicit merchant approval, protecting INV-OD-07."""
        self._ensure_pending_review()
        self._status = DetectionCandidateStatus.PROMOTED

    def reject(self) -> None:
        """Record one explicit merchant rejection, protecting INV-OD-07."""
        self._ensure_pending_review()
        self._status = DetectionCandidateStatus.REJECTED

    def reassign_contact(self, contact_id: UUID) -> None:
        """Reassign this candidate after a CRM Contact merge (INV-CRM-03, INV-TR-01)."""
        self.contact_id = contact_id

    def _ensure_pending_review(self) -> None:
        """Protect the one-time review decision required by INV-OD-07."""
        if self._status is not DetectionCandidateStatus.PENDING_REVIEW:
            raise DetectionCandidateAlreadyReviewedException(
                "Detection candidate has already been reviewed."
            )

    @property
    def status(self) -> DetectionCandidateStatus:
        """Return the review state without exposing a direct state mutation path."""
        return self._status

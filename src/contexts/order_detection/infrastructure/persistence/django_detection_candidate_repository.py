"""Module: contexts/order_detection/infrastructure/django_detection_candidate_repository.py
Context: Order Detection.
Role: map DetectionCandidate aggregates to PostgreSQL records.
"""

from decimal import Decimal
from uuid import UUID

from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money

from ...domain.entities.detection_candidate import DetectionCandidate, DetectionCandidateStatus
from .models import DetectionCandidateRecord


class DjangoDetectionCandidateRepository:
    """Persist and rehydrate DetectionCandidate without leaking ORM into the domain."""

    def save(self, candidate: DetectionCandidate) -> None:
        """Insert/update a candidate inside the caller's atomic unit of work."""
        DetectionCandidateRecord.objects.update_or_create(
            id=candidate.id,
            defaults={
                "merchant_id": candidate.merchant_id,
                "contact_id": candidate.contact_id,
                "detected_amount": candidate.detected_amount.amount,
                "currency": candidate.detected_amount.currency,
                "confidence_score": candidate.confidence_score.value,
                "source_message_id": candidate.source_message_id,
                "matched_rule_ids": [str(value) for value in candidate.matched_rule_ids],
                "status": candidate.status.value,
                "created_at": candidate.created_at,
            },
        )

    def find_by_id(self, candidate_id: UUID) -> DetectionCandidate | None:
        """Load one candidate for a scoped manual decision."""
        record = DetectionCandidateRecord.objects.filter(id=candidate_id).first()
        if record is None:
            return None
        return DetectionCandidate(
            id=record.id,
            merchant_id=record.merchant_id,
            contact_id=record.contact_id,
            detected_amount=Money(Decimal(record.detected_amount), record.currency),
            confidence_score=ConfidenceScore(record.confidence_score),
            source_message_id=record.source_message_id,
            matched_rule_ids=tuple(UUID(value) for value in record.matched_rule_ids),
            _status=DetectionCandidateStatus(record.status),
            created_at=record.created_at,
        )

    def find_for_update_by_id(self, candidate_id: UUID) -> DetectionCandidate | None:
        """Lock and rehydrate one candidate for an isolated aggregate transaction."""
        record = DetectionCandidateRecord.objects.select_for_update().filter(
            id=candidate_id
        ).first()
        return self._to_domain(record) if record else None

    def find_ids_by_contact(self, contact_id: UUID) -> list[UUID]:
        """Return stable candidate IDs still pointing at the specified Contact."""
        return list(
            DetectionCandidateRecord.objects.filter(contact_id=contact_id)
            .order_by("id")
            .values_list("id", flat=True)
        )

    def find_pending_by_merchant(
        self,
        merchant_id: UUID,
        offset: int,
        limit: int,
    ) -> tuple[list[DetectionCandidate], int]:
        """Return only the merchant's pending candidates in stable oldest-first order."""
        pending_records = DetectionCandidateRecord.objects.filter(
            merchant_id=merchant_id,
            status=DetectionCandidateStatus.PENDING_REVIEW.value,
        )
        total_count = pending_records.count()
        page_records = pending_records.order_by("created_at", "id")[offset : offset + limit]
        candidates = [
            DetectionCandidate(
                id=record.id,
                merchant_id=record.merchant_id,
                contact_id=record.contact_id,
                detected_amount=Money(Decimal(record.detected_amount), record.currency),
                confidence_score=ConfidenceScore(record.confidence_score),
                source_message_id=record.source_message_id,
                matched_rule_ids=tuple(UUID(value) for value in record.matched_rule_ids),
                _status=DetectionCandidateStatus(record.status),
                created_at=record.created_at,
            )
            for record in page_records
        ]
        return candidates, total_count

    @staticmethod
    def _to_domain(record: DetectionCandidateRecord) -> DetectionCandidate:
        """Rehydrate one candidate without exposing its persistence model."""
        return DetectionCandidate(
            id=record.id,
            merchant_id=record.merchant_id,
            contact_id=record.contact_id,
            detected_amount=Money(Decimal(record.detected_amount), record.currency),
            confidence_score=ConfidenceScore(record.confidence_score),
            source_message_id=record.source_message_id,
            matched_rule_ids=tuple(UUID(value) for value in record.matched_rule_ids),
            _status=DetectionCandidateStatus(record.status),
            created_at=record.created_at,
        )
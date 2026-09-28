from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from shared_kernel.application_exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

from ..domain.detection_candidate import DetectionCandidate
from ..domain.i_detection_candidate_repository import IDetectionCandidateRepository
from .events import (
    DetectionCandidatePromoted,
    DetectionCandidateRejected,
    DetectionCorrectedByMerchant,
)
from .ports import IOrderDetectionOutbox, IOrderDetectionUnitOfWork


class DetectionDecision(StrEnum):
    """Merchant decisions accepted by the candidate review use case."""

    VALIDATE = "validate"
    REJECT = "reject"


@dataclass(frozen=True)
class ValidateOrRejectDetectionResult:
    """Result of recording a merchant's one-time candidate decision."""

    candidate_id: UUID
    status: str


class ValidateOrRejectDetectionUseCase:
    """Record a candidate decision and publish events without modifying an Order.

    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.
    A validated candidate is consumed asynchronously by the Order-creation use case,
    keeping this transaction limited to the DetectionCandidate aggregate (INV-TR-01).

    Args:
        candidate_repository: persistence port for DetectionCandidate only.
        unit_of_work: transaction boundary shared by the candidate and its outbox rows.
        outbox: writes promotion/rejection and rule-feedback events transactionally.

    Returns:
        The candidate identifier and its terminal state (`promoted` or `rejected`).

    Raises:
        ResourceNotFoundException: if the candidate is absent or belongs to another merchant.
        ValidationException: if decision is not `validate` or `reject`.
        DetectionCandidateAlreadyReviewedException: if a terminal decision already exists.

    Protects INV-OD-07 and INV-TR-01/02.
    """

    def __init__(
        self,
        candidate_repository: IDetectionCandidateRepository,
        unit_of_work: IOrderDetectionUnitOfWork,
        outbox: IOrderDetectionOutbox,
    ) -> None:
        """Receive candidate persistence and transactional event dependencies."""
        self._candidate_repository = candidate_repository
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(
        self, candidate_id: UUID, decision: str, merchant_id: UUID
    ) -> ValidateOrRejectDetectionResult:
        """Persist one scoped decision and its outbox events atomically."""
        try:
            normalized_decision = DetectionDecision(decision)
        except ValueError as error:
            raise ValidationException("Decision must be 'validate' or 'reject'.") from error

        with self._unit_of_work:
            candidate = self._candidate_repository.find_by_id(candidate_id)
            if candidate is None or candidate.merchant_id != merchant_id:
                raise ResourceNotFoundException("Detection candidate was not found.")

            if normalized_decision is DetectionDecision.VALIDATE:
                candidate.promote()
                self._candidate_repository.save(candidate)
                self._outbox.add(
                    DetectionCandidatePromoted(
                        candidate_id=candidate.id,
                        merchant_id=candidate.merchant_id,
                        contact_id=candidate.contact_id,
                        source_message_id=candidate.source_message_id,
                        detected_amount=candidate.detected_amount,
                        confidence_score=candidate.confidence_score,
                        matched_rule_ids=candidate.matched_rule_ids,
                        event_id=uuid4(),
                        occurred_at=datetime.now(timezone.utc),
                    )
                )
                was_correct = True
            else:
                candidate.reject()
                self._candidate_repository.save(candidate)
                self._outbox.add(
                    DetectionCandidateRejected(
                        candidate_id=candidate.id,
                        merchant_id=candidate.merchant_id,
                    )
                )
                was_correct = False

            for rule_id in candidate.matched_rule_ids:
                self._outbox.add(
                    DetectionCorrectedByMerchant(
                        merchant_id=candidate.merchant_id,
                        rule_id=rule_id,
                        was_correct=was_correct,
                    )
                )

        return ValidateOrRejectDetectionResult(
            candidate_id=candidate.id,
            status=candidate.status.value,
        )
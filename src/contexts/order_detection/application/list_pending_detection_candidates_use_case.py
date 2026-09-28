from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.application_exceptions import ValidationException
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money

from ..domain.i_detection_candidate_repository import IDetectionCandidateRepository


@dataclass(frozen=True)
class DetectionCandidateSummary:
    """Read-only manual-review candidate details exposed by the application contract."""

    candidate_id: UUID
    contact_id: UUID
    detected_amount: Money
    confidence_score: ConfidenceScore
    source_message_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class ListPendingDetectionCandidatesResult:
    """One stable page of pending candidates and the merchant-scoped total count."""

    candidates: tuple[DetectionCandidateSummary, ...]
    total_count: int


class ListPendingDetectionCandidatesUseCase:
    """List one merchant's pending manual detections without mutating aggregates.

    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.
    The repository scopes by merchant and pending-review state, with stable oldest-first
    ordering. Defaults are page 1 and 50 rows; page size is capped at 100.

    Args:
        candidate_repository: merchant-scoped pending-candidate read port.

    Returns:
        Candidate summaries and the total number of pending candidates for that merchant.

    Raises:
        ValidationException: when page or page size is outside the catalogued contract.

    Protects INV-OD-04 and INV-OD-07.
    """

    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 100

    def __init__(
        self,
        candidate_repository: IDetectionCandidateRepository,
    ) -> None:
        """Receive the read repository through its application port."""
        self._candidate_repository = candidate_repository

    def execute(
        self,
        merchant_id: UUID,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> ListPendingDetectionCandidatesResult:
        """Validate pagination and project the selected page to read-only summaries."""
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValidationException("Page must be a positive integer.")
        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size < 1
            or page_size > self.MAX_PAGE_SIZE
        ):
            raise ValidationException("Page size must be between 1 and 100.")

        offset = (page - 1) * page_size
        candidates, total_count = self._candidate_repository.find_pending_by_merchant(
            merchant_id=merchant_id,
            offset=offset,
            limit=page_size,
        )
        summaries = tuple(
            DetectionCandidateSummary(
                candidate_id=candidate.id,
                contact_id=candidate.contact_id,
                detected_amount=candidate.detected_amount,
                confidence_score=candidate.confidence_score,
                source_message_id=candidate.source_message_id,
                created_at=candidate.created_at,
            )
            for candidate in candidates
        )
        return ListPendingDetectionCandidatesResult(
            candidates=summaries,
            total_count=total_count,
        )
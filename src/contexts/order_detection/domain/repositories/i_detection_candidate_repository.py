from typing import Protocol
from uuid import UUID

from ..entities.detection_candidate import DetectionCandidate


class IDetectionCandidateRepository(Protocol):
    """Persistence port for manual-review candidates, separate from Orders."""

    def save(self, candidate: DetectionCandidate) -> None:
        """Persist one candidate inside the caller's unit of work."""

    def find_by_id(self, candidate_id: UUID) -> DetectionCandidate | None:
        """Load a candidate for a single-aggregate decision transaction."""

    def find_for_update_by_id(self, candidate_id: UUID) -> DetectionCandidate | None:
        """Load and lock one candidate for its own transaction (INV-TR-01)."""

    def find_ids_by_contact(self, contact_id: UUID) -> list[UUID]:
        """List candidate IDs still referencing a merged Contact for resumable reassignment."""

    def find_pending_by_merchant(
        self,
        merchant_id: UUID,
        offset: int,
        limit: int,
    ) -> tuple[list[DetectionCandidate], int]:
        """Return one page of pending candidates and the total count for that merchant."""
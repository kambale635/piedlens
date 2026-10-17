from typing import Protocol
from uuid import UUID

from ..entities.segment import CRMSegment


class ISegmentRepository(Protocol):
    """Persistence port for merchant-scoped CRM segments."""

    def save(self, segment: CRMSegment) -> None:
        """Persist a segment aggregate in the same transaction as its use case."""

    def find_by_id(self, segment_id: UUID) -> CRMSegment | None:
        """Load one persisted segment for membership evaluation."""

    def find_by_merchant(self, merchant_id: UUID) -> list[CRMSegment]:
        """Return all segments for one merchant, mainly for list/report queries."""

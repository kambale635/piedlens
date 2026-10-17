from dataclasses import dataclass
from uuid import UUID, uuid4

from ..value_objects.segment_rule import SegmentRule


@dataclass
class CRMSegment:
    """Aggregate root for a merchant-scoped dynamic CRM segment."""

    id: UUID
    merchant_id: UUID
    name: str
    definition_rule: SegmentRule

    @classmethod
    def create(
        cls,
        merchant_id: UUID,
        name: str,
        definition_rule: SegmentRule,
    ) -> "CRMSegment":
        """Create a dynamic segment whose membership is evaluated by the domain service."""
        return cls(
            id=uuid4(),
            merchant_id=merchant_id,
            name=name,
            definition_rule=definition_rule,
        )

from __future__ import annotations

from uuid import UUID

from ..domain.contact import Contact
from ..domain.i_contact_repository import IContactRepository
from ..domain.i_segment_repository import ISegmentRepository
from ..domain.segment_membership_calculator import SegmentMembershipCalculator


class GetSegmentMembersUseCase:
    """Return the Contact members of a CRM segment for a merchant and page."""

    def __init__(
        self,
        contact_repository: IContactRepository,
        segment_repository: ISegmentRepository,
    ) -> None:
        """Inject the contact and segment persistence ports through the constructor."""
        self._contact_repository = contact_repository
        self._segment_repository = segment_repository
        self._calculator = SegmentMembershipCalculator()

    def execute(self, segment_id: UUID, page: int = 1, page_size: int = 50) -> dict:
        """Resolve a merchant segment and return the matching contacts for a page."""
        segment = self._segment_repository.find_by_id(segment_id)
        if segment is None:
            return {"contacts": [], "total_count": 0}

        contacts = self._contact_repository.find_by_merchant(segment.merchant_id)
        matched = self._calculator.evaluate(segment.definition_rule, contacts)

        start = (page - 1) * page_size
        end = start + page_size
        page_contacts = matched[start:end]

        return {
            "contacts": [self._serialize(contact) for contact in page_contacts],
            "total_count": len(matched),
        }

    @staticmethod
    def _serialize(contact: Contact) -> dict:
        """Project a Contact aggregate to a pagination-safe summary payload."""
        return {
            "contact_id": contact.id,
            "display_name": contact.display_name,
            "external_identifier": contact.external_identifier,
            "loyalty_score": contact.loyalty_score.value,
            "order_count": contact.order_count,
        }

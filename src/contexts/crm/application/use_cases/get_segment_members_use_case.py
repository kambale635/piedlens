from __future__ import annotations

from uuid import UUID

from ...domain.entities.contact import Contact
from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.repositories.i_segment_repository import ISegmentRepository
from ...domain.services.segment_membership_calculator import SegmentMembershipCalculator
from ..exceptions import InvalidSegmentPaginationException, SegmentNotFoundException
from ..ports import ICRMSegmentMembershipCache


class GetSegmentMembersUseCase:
    """Return the Contact members of a CRM segment for a merchant and page."""

    def __init__(
        self,
        contact_repository: IContactRepository,
        segment_repository: ISegmentRepository,
        membership_cache: ICRMSegmentMembershipCache,
    ) -> None:
        """Inject the contact and segment persistence ports through the constructor."""
        self._contact_repository = contact_repository
        self._segment_repository = segment_repository
        self._membership_cache = membership_cache
        self._calculator = SegmentMembershipCalculator()

    def execute(
        self,
        segment_id: UUID,
        page: int = 1,
        page_size: int = 50,
        merchant_id: UUID | None = None,
    ) -> dict:
        """Resolve a merchant segment and return the matching contacts for a page."""
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 1
            or isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size < 1
        ):
            raise InvalidSegmentPaginationException("Page and page_size must be positive integers.")
        segment = self._segment_repository.find_by_id(segment_id)
        if segment is None or (merchant_id is not None and segment.merchant_id != merchant_id):
            raise SegmentNotFoundException("CRM segment was not found.")

        cached_result = self._membership_cache.get_members(
            segment_id,
            segment.merchant_id,
            page,
            page_size,
        )
        if cached_result is not None:
            return cached_result

        contacts = self._contact_repository.find_by_merchant(segment.merchant_id)
        matched = self._calculator.evaluate(segment.definition_rule, contacts)

        start = (page - 1) * page_size
        end = start + page_size
        page_contacts = matched[start:end]

        result = {
            "contacts": [self._serialize(contact) for contact in page_contacts],
            "total_count": len(matched),
        }
        self._membership_cache.set_members(
            segment_id,
            segment.merchant_id,
            page,
            page_size,
            result,
        )
        return result

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

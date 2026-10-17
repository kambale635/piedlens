from uuid import UUID

from ...domain.entities.contact import Contact
from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.repositories.i_segment_repository import ISegmentRepository
from ...domain.services.segment_membership_calculator import SegmentMembershipCalculator
from ..exceptions import InvalidSegmentPaginationException, SegmentNotFoundException


class ListContactsUseCase:
    """List a merchant's CRM contacts, optionally filtered by a dynamic segment.

    Contract: docs/15-use-cases-catalog.md#contexte-crm.
    Contacts and segments are restricted to the merchant scope supplied by the
    tenant middleware. Segment membership is calculated dynamically (INV-CRM-02);
    identity is based on the external identifier, never display name (INV-CRM-01).
    """

    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 100

    def __init__(
        self,
        contact_repository: IContactRepository,
        segment_repository: ISegmentRepository,
    ) -> None:
        """Receive CRM-owned read repositories through application ports."""
        self._contact_repository = contact_repository
        self._segment_repository = segment_repository
        self._membership_calculator = SegmentMembershipCalculator()

    def execute(
        self,
        merchant_id: UUID,
        segment_id: UUID | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """Return one stable page of contacts scoped to the requested merchant."""
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 1
            or isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size < 1
            or page_size > self.MAX_PAGE_SIZE
        ):
            raise InvalidSegmentPaginationException("Page values are outside the supported range.")

        contacts = self._contact_repository.find_by_merchant(merchant_id)
        if segment_id is not None:
            segment = self._segment_repository.find_by_id(segment_id)
            if segment is None or segment.merchant_id != merchant_id:
                raise SegmentNotFoundException("CRM segment was not found.")
            contacts = self._membership_calculator.evaluate(segment.definition_rule, contacts)

        start = (page - 1) * page_size
        return {
            "contacts": [self._serialize(contact) for contact in contacts[start:start + page_size]],
            "total_count": len(contacts),
        }

    @staticmethod
    def _serialize(contact: Contact) -> dict:
        """Project a Contact aggregate to a compact, read-only route summary."""
        return {
            "contact_id": contact.id,
            "display_name": contact.display_name,
            "external_identifier": contact.external_identifier,
            "loyalty_score": contact.loyalty_score.value,
            "order_count": contact.order_count,
        }
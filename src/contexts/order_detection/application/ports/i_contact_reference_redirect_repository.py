from typing import Protocol
from uuid import UUID


class IContactReferenceRedirectRepository(Protocol):
    """Order Detection-owned view of merged Contact identity redirects."""

    def register(
        self,
        merchant_id: UUID,
        merged_contact_id: UUID,
        primary_contact_id: UUID,
    ) -> None:
        """Persist one CRM-issued redirect in the active Order Detection transaction."""

    def resolve(self, merchant_id: UUID, contact_id: UUID) -> UUID:
        """Resolve a contact ID through all redirects known to this context."""
from typing import Protocol
from uuid import UUID

from ..entities.contact import Contact


class IContactRepository(Protocol):
    """Persistence port for merchant-scoped CRM contacts."""

    def find_by_external_identifier(
        self,
        merchant_id: UUID,
        platform_connection_id: UUID,
        external_identifier: str,
    ) -> Contact | None:
        """Find by the complete CRM identity key, never by display name (INV-CRM-01)."""

    def find_for_update_by_external_identifier(
        self,
        merchant_id: UUID,
        platform_connection_id: UUID,
        external_identifier: str,
    ) -> Contact | None:
        """Load and lock the identity row to prevent concurrent timestamp regression."""

    def find_for_update_by_id(self, contact_id: UUID) -> Contact | None:
        """Load and lock one Contact aggregate for an OrderStatusChanged consumer."""

    def find_by_id(self, contact_id: UUID) -> Contact | None:
        """Load one Contact for campaign delivery without mutating its aggregate."""

    def find_by_merchant(self, merchant_id: UUID) -> list[Contact]:
        """Return CRM-owned Contact aggregates for a scheduled merchant job."""

    def get_or_create(self, contact: Contact) -> tuple[Contact, bool]:
        """Atomically create by identity key or return the existing aggregate."""

    def save(self, contact: Contact) -> None:
        """Persist one Contact aggregate inside the caller's transaction."""
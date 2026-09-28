from typing import Protocol
from uuid import UUID

from .order import Order


class IOrderRepository(Protocol):
    """Persistence port for Order aggregates owned by Order Detection."""

    def save(self, order: Order) -> None:
        """Persist one Order; source_candidate_id must have a unique constraint."""

    def find_by_id(self, order_id: UUID) -> Order | None:
        """Load an Order aggregate by its identifier."""

    def find_pending_by_contact(self, contact_id: UUID, within_days: int) -> list[Order]:
        """Return open Orders for a contact in the window, newest first (INV-OD-02)."""

    def find_by_source_candidate_id(self, candidate_id: UUID) -> Order | None:
        """Find the Order already created for a promoted candidate, if any."""

    def find_dormant(self, merchant_id: UUID, older_than_hours: int) -> list[Order]:
        """Return a merchant's old open Orders, oldest first and amount descending."""
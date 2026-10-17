from typing import Protocol
from uuid import UUID

from shared_kernel.value_objects.money import Money


class IContactDefaultsProvider(Protocol):
    """Resolve merchant-specific initial values without crossing into Identity directly."""

    def initial_total_spent(self, merchant_id: UUID) -> Money:
        """Return zero Money in the merchant's configured currency."""

    def primary_currency(self, merchant_id: UUID) -> str:
        """Return the merchant's configured primary currency for loyalty scoring (INV-CRM-08)."""
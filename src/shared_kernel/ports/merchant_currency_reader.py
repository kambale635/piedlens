from typing import Protocol
from uuid import UUID


class IMerchantCurrencyReader(Protocol):
    """Read a merchant's configured primary currency without importing Identity models."""

    def currency_for(self, merchant_id: UUID) -> str: ...
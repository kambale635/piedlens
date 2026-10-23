from datetime import date
from typing import Protocol
from uuid import UUID


class IOrderValueReportReader(Protocol):
    """Read reported-to-follow-up and paid transition amounts from Order Detection."""

    def monthly_order_amounts(self, merchant_id: UUID, month: date) -> dict[str, list[dict]]: ...


class IPaidPeriodPriceReader(Protocol):
    """Read an actual recorded subscription payment, never a catalog list price."""

    def actual_paid_price(self, merchant_id: UUID, month: date) -> dict | None: ...
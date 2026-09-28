from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.application_exceptions import ValidationException
from shared_kernel.value_objects.money import Money

from ..domain.i_order_repository import IOrderRepository
from ..domain.order import Order
from ..domain.order_status import OrderStatus


@dataclass(frozen=True)
class OrderSummary:
    """Read-only order details needed by the dormant-money dashboard."""

    order_id: UUID
    contact_id: UUID
    amount: Money
    status: str
    created_at: datetime


@dataclass(frozen=True)
class DormantMoneyDashboardResult:
    """Dashboard totals grouped by currency, with no implicit FX conversion."""

    totals_by_currency: tuple[Money, ...]
    orders: tuple[OrderSummary, ...]


class GetDormantMoneyDashboardUseCase:
    """Read a merchant's old open orders and aggregate money by currency.

    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.
    Only `pending_payment` and `paid_not_delivered` orders qualify; cancelled and
    delivered orders are excluded by the repository query.

    Args:
        order_repository: read port returning the merchant's qualifying orders.

    Returns:
        Per-currency `Money` totals and ordered order summaries.

    Raises:
        ValidationException: if `older_than_hours` is not a positive integer.

    Protects INV-OD-05 and INV-TR-05.
    """

    def __init__(self, order_repository: IOrderRepository) -> None:
        """Receive the Order Detection read repository through its port."""
        self._order_repository = order_repository

    def execute(
        self, merchant_id: UUID, older_than_hours: int = 24
    ) -> DormantMoneyDashboardResult:
        """Build a per-currency dashboard without adding bare numeric amounts."""
        if (
            isinstance(older_than_hours, bool)
            or not isinstance(older_than_hours, int)
            or older_than_hours <= 0
        ):
            raise ValidationException("older_than_hours must be a positive integer.")

        orders = self._order_repository.find_dormant(merchant_id, older_than_hours)
        totals: dict[str, Money] = {}
        summaries: list[OrderSummary] = []

        for order in orders:
            if order.status not in {
                OrderStatus.PENDING_PAYMENT,
                OrderStatus.PAID_NOT_DELIVERED,
            }:
                continue

            amount = order.detected_amount
            if amount.currency in totals:
                totals[amount.currency] = totals[amount.currency].add(amount)
            else:
                totals[amount.currency] = amount

            summaries.append(
                OrderSummary(
                    order_id=order.id,
                    contact_id=order.contact_id,
                    amount=amount,
                    status=order.status.value,
                    created_at=order.created_at,
                )
            )

        return DormantMoneyDashboardResult(
            totals_by_currency=tuple(totals[currency] for currency in sorted(totals)),
            orders=tuple(summaries),
        )
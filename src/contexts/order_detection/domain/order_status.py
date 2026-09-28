from enum import StrEnum


class OrderStatus(StrEnum):
    """Lifecycle states allowed for an Order aggregate (INV-OD-01)."""

    PENDING_PAYMENT = "pending_payment"
    PAID_NOT_DELIVERED = "paid_not_delivered"
    PAID_AND_DELIVERED = "paid_and_delivered"
    CANCELLED = "cancelled"
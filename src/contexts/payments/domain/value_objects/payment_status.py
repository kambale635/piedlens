from enum import StrEnum


class PaymentStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    NEEDS_REVIEW = "needs_review"
    DUPLICATE_PAYMENT = "duplicate_payment"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"

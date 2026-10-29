from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..events.payment_events import PaymentSucceeded
from ..exceptions.payment_exceptions import InvalidPaymentTransition
from ..value_objects.payment_proof_status import PaymentProofStatus
from ..value_objects.payment_status import PaymentStatus


@dataclass
class PaymentAttempt:
    """One immutable-amount payment lifecycle owned by Payments (INV-PAY-01..07)."""

    id: UUID
    merchant_id: UUID
    payable_type: str
    payable_id: UUID
    payable_reference: str
    provider_code: str
    amount_minor: int
    currency: str
    fee_minor: int
    status: PaymentStatus
    provider_reference: str | None
    proof_status: PaymentProofStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if isinstance(self.amount_minor, bool) or self.amount_minor < 0:
            raise ValueError("Payment amount must be non-negative integer minor units. INV-PAY-01")
        if isinstance(self.fee_minor, bool) or self.fee_minor < 0:
            raise ValueError("Payment fee must be non-negative integer minor units. INV-PAY-05")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("Payment currency must be explicit ISO code. INV-PAY-01")

    def mark_pending(self, provider_reference: str | None, occurred_at: datetime) -> None:
        if self.status != PaymentStatus.CREATED:
            raise InvalidPaymentTransition("Only created attempts can become pending. INV-PAY-06")
        self.status = PaymentStatus.PENDING
        self.provider_reference = provider_reference
        self.updated_at = occurred_at

    def apply_provider_result(self, *, event_amount_minor: int, event_currency: str,
                              outcome: str, provider_reference: str, occurred_at: datetime):
        """Apply a matching verified provider result; mismatches or late events need review (INV-PAY-01/06/07)."""
        if event_amount_minor != self.amount_minor or event_currency.upper() != self.currency.upper():
            self.status = PaymentStatus.NEEDS_REVIEW
            self.updated_at = occurred_at
            return "needs_review"
        if self.status in {PaymentStatus.EXPIRED, PaymentStatus.CANCELLED, PaymentStatus.FAILED}:
            self.status = PaymentStatus.NEEDS_REVIEW
            self.updated_at = occurred_at
            return None
        if self.status == PaymentStatus.SUCCEEDED:
            self.status = PaymentStatus.DUPLICATE_PAYMENT
            self.updated_at = occurred_at
            return "duplicate_payment"
        if self.status != PaymentStatus.PENDING:
            raise InvalidPaymentTransition("Provider result requires a pending attempt. INV-PAY-06")
        self.provider_reference = provider_reference
        self.updated_at = occurred_at
        if outcome == "pending":
            return None
        if outcome == "failed":
            self.status = PaymentStatus.FAILED
            return None
        if outcome != "succeeded":
            raise InvalidPaymentTransition("Unknown provider result. INV-PAY-06")
        self.status = PaymentStatus.SUCCEEDED
        self.proof_status = PaymentProofStatus.PROVIDER_CONFIRMED
        return PaymentSucceeded.create(
            self.id, self.merchant_id, self.payable_type, self.payable_id,
            self.payable_reference, self.amount_minor, self.currency, self.fee_minor, occurred_at,
        )

    def apply_unverified_proof(self, occurred_at: datetime) -> None:
        """Record unverified evidence without confirming payment (INV-PAY-03)."""
        if self.status not in {PaymentStatus.CREATED, PaymentStatus.PENDING}:
            raise InvalidPaymentTransition("Proof cannot change a terminal attempt. INV-PAY-06")
        self.proof_status = PaymentProofStatus.UNVERIFIED
        self.updated_at = occurred_at

    def confirm_seller_proof(self, occurred_at: datetime):
        """Accept an explicit seller confirmation, never an unverified SMS/capture (INV-PAY-03)."""
        if self.status != PaymentStatus.PENDING:
            raise InvalidPaymentTransition("Seller confirmation requires pending attempt. INV-PAY-06")
        self.status = PaymentStatus.SUCCEEDED
        self.proof_status = PaymentProofStatus.SELLER_CONFIRMED
        self.updated_at = occurred_at
        return PaymentSucceeded.create(
            self.id, self.merchant_id, self.payable_type, self.payable_id,
            self.payable_reference, self.amount_minor, self.currency, self.fee_minor, occurred_at,
        )

    def expire(self, occurred_at: datetime) -> None:
        if self.status == PaymentStatus.PENDING and occurred_at >= self.expires_at:
            self.status = PaymentStatus.EXPIRED
            self.updated_at = occurred_at

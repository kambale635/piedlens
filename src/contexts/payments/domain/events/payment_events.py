from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

@dataclass(frozen=True)
class PaymentSucceeded:
    """Signals verified payment to the owning payable context (INV-PAY-02/05)."""

    event_id: UUID
    payment_attempt_id: UUID
    merchant_id: UUID
    payable_type: str
    payable_id: UUID
    payable_reference: str
    amount_minor: int
    currency: str
    fee_minor: int
    occurred_at: datetime

    @classmethod
    def create(cls, payment_attempt_id, merchant_id, payable_type, payable_id, payable_reference, amount_minor, currency, fee_minor, occurred_at):
        return cls(uuid4(), payment_attempt_id, merchant_id, payable_type, payable_id, payable_reference, amount_minor, currency, fee_minor, occurred_at)


@dataclass(frozen=True)
class ExternalPaymentReceived:
    """Normalized verified external payment signal (INV-PAY-01/02/06)."""

    event_id: UUID
    payment_attempt_id: UUID
    provider_code: str
    provider_event_id: str
    merchant_id: UUID
    amount_minor: int
    currency: str
    outcome: str
    provider_reference: str
    occurred_at: datetime

    @classmethod
    def create(cls, payment_attempt_id, provider_code, provider_event_id, merchant_id,
               amount_minor, currency, outcome, provider_reference, occurred_at):
        return cls(uuid4(), payment_attempt_id, provider_code, provider_event_id,
                   merchant_id, amount_minor, currency, outcome, provider_reference, occurred_at)


@dataclass(frozen=True)
class PaymentRefundRequested:
    """Requests compensation for a duplicate successful payment (INV-PAY-02)."""

    event_id: UUID
    payment_attempt_id: UUID
    payable_id: UUID
    provider_reference: str
    occurred_at: datetime

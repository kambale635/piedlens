from enum import StrEnum


class PaymentProofStatus(StrEnum):
    UNVERIFIED = "unverified"
    SELLER_CONFIRMED = "seller_confirmed"
    PROVIDER_CONFIRMED = "provider_confirmed"

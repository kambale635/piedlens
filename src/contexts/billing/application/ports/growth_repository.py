from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class TrialPolicy:
    enabled: bool
    duration_days: int
    target_plan_code: str
    card_required: bool


@dataclass(frozen=True)
class CouponTerms:
    code: str
    discount_percent: int
    duration_days: int
    max_redemptions: int | None
    redemption_count: int
    valid_from: datetime
    valid_until: datetime | None
    is_active: bool


@dataclass(frozen=True)
class ReferralPolicy:
    reward_percent: int
    reward_duration_days: int
    max_referrals_per_merchant: int


@dataclass(frozen=True)
class Referral:
    referrer_merchant_id: UUID
    referred_merchant_id: UUID
    reward_percent: int
    reward_duration_days: int


class IBillingGrowthRepository(Protocol):
    """Persist trial, coupon, and referral aggregates in Billing-owned storage."""

    def lock_merchant(self, merchant_id: UUID) -> None: ...

    def trial_policy(self) -> TrialPolicy: ...

    def has_ever_started_trial(self, merchant_id: UUID) -> bool: ...

    def create_trial(self, merchant_id, target_plan_code, starts_at, ends_at, card_required, card_present) -> None: ...

    def lock_coupon(self, code: str) -> CouponTerms | None: ...

    def merchant_has_redeemed_coupon(self, merchant_id: UUID, coupon_code: str) -> bool: ...

    def record_coupon_redemption(self, merchant_id, coupon_code, redeemed_at, expires_at) -> None: ...

    def referral_policy(self) -> ReferralPolicy: ...

    def referral_exists_for_merchant(self, referred_merchant_id: UUID) -> bool: ...

    def count_referrals(self, referrer_merchant_id: UUID) -> int: ...

    def create_referral(self, referrer_merchant_id, referred_merchant_id, created_at, policy) -> Referral: ...

    def create_first_paid_period(
        self, merchant_id: UUID, paid_at: datetime, paid_amount_minor: int | None, currency: str | None
    ) -> bool: ...

    def referral_for_referred_merchant(self, merchant_id: UUID) -> Referral | None: ...

    def mark_referral_rewarded(self, merchant_id: UUID, paid_at: datetime) -> Referral | None: ...


class IBillingUnitOfWork(Protocol):
    """Define the transaction containing Billing records and their Outbox event."""

    def __enter__(self): ...

    def __exit__(self, exception_type, exception, traceback): ...


class IBillingOutbox(Protocol):
    """Append a Billing event to its transactional Outbox."""

    def add(self, event: object) -> None: ...
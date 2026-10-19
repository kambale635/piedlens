from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class CouponRedeemed:
    event_id: UUID
    occurred_at: datetime
    merchant_id: UUID
    coupon_code: str
    discount_percent: int
    expires_at: datetime

    @classmethod
    def create(cls, merchant_id, coupon_code, discount_percent, expires_at, occurred_at):
        """Build a coupon event without exposing payment or customer data."""
        return cls(uuid4(), occurred_at, merchant_id, coupon_code, discount_percent, expires_at)


@dataclass(frozen=True)
class ReferralRewardGranted:
    event_id: UUID
    occurred_at: datetime
    referrer_merchant_id: UUID
    referred_merchant_id: UUID
    reward_percent: int
    reward_duration_days: int

    @classmethod
    def create(cls, referral, occurred_at):
        """Build the first-paid-period reward event for one referred merchant."""
        return cls(
            uuid4(),
            occurred_at,
            referral.referrer_merchant_id,
            referral.referred_merchant_id,
            referral.reward_percent,
            referral.reward_duration_days,
        )
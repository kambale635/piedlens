from datetime import datetime
from typing import Protocol


class IBillingGrowthAdminRepository(Protocol):
    """Persist administrator-managed trial, referral, and coupon configuration."""

    def upsert_trial_policy(self, enabled, duration_days, target_plan_code, card_required) -> dict: ...

    def upsert_referral_policy(self, reward_percent, reward_duration_days, max_referrals) -> dict: ...

    def upsert_coupon(
        self,
        code,
        discount_percent,
        duration_days,
        max_redemptions,
        valid_from: datetime,
        valid_until: datetime | None,
        is_active,
    ) -> dict: ...
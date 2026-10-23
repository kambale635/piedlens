from django.db import transaction
from django.utils import timezone

from ...application.ports.growth_repository import (
    CouponTerms,
    Referral,
    ReferralPolicy,
    TrialPolicy,
)
from .models import (
    BillingMerchantLockRecord,
    CouponRecord,
    CouponRedemptionRecord,
    PaidPeriodRecord,
    ReferralPolicyRecord,
    ReferralRecord,
    TrialPolicyRecord,
    TrialRecord,
)


class DjangoBillingGrowthRepository:
    """Implement transactional trial, coupon and referral storage owned by Billing."""

    def lock_merchant(self, merchant_id):
        BillingMerchantLockRecord.objects.get_or_create(merchant_id=merchant_id)
        BillingMerchantLockRecord.objects.select_for_update().get(merchant_id=merchant_id)

    def trial_policy(self):
        policy = TrialPolicyRecord.objects.get(policy_key="default")
        return TrialPolicy(
            policy.enabled,
            policy.duration_days,
            policy.target_plan_code,
            policy.card_required,
        )

    def has_ever_started_trial(self, merchant_id):
        return TrialRecord.objects.filter(merchant_id=merchant_id).exists()

    def create_trial(
        self, merchant_id, target_plan_code, starts_at, ends_at, card_required, card_present
    ):
        TrialRecord.objects.create(
            merchant_id=merchant_id,
            target_plan_code=target_plan_code,
            starts_at=starts_at,
            ends_at=ends_at,
            card_required=card_required,
            card_present=card_present,
        )

    def lock_coupon(self, code):
        coupon = CouponRecord.objects.select_for_update().filter(code=code).first()
        if coupon is None:
            return None
        return CouponTerms(
            coupon.code,
            coupon.discount_percent,
            coupon.duration_days,
            coupon.max_redemptions,
            coupon.redemption_count,
            coupon.valid_from,
            coupon.valid_until,
            coupon.is_active,
        )

    def merchant_has_redeemed_coupon(self, merchant_id, coupon_code):
        return CouponRedemptionRecord.objects.filter(
            merchant_id=merchant_id, coupon__code=coupon_code
        ).exists()

    def record_coupon_redemption(self, merchant_id, coupon_code, redeemed_at, expires_at):
        coupon = CouponRecord.objects.select_for_update().get(code=coupon_code)
        CouponRedemptionRecord.objects.create(
            coupon=coupon,
            merchant_id=merchant_id,
            redeemed_at=redeemed_at,
            expires_at=expires_at,
            discount_percent=coupon.discount_percent,
            duration_days=coupon.duration_days,
        )
        coupon.redemption_count += 1
        coupon.save(update_fields=["redemption_count"])

    def referral_policy(self):
        policy = ReferralPolicyRecord.objects.get(policy_key="default")
        return ReferralPolicy(
            policy.reward_percent,
            policy.reward_duration_days,
            policy.max_referrals_per_merchant,
        )

    def referral_exists_for_merchant(self, referred_merchant_id):
        return ReferralRecord.objects.filter(referred_merchant_id=referred_merchant_id).exists()

    def count_referrals(self, referrer_merchant_id):
        return ReferralRecord.objects.filter(referrer_merchant_id=referrer_merchant_id).count()

    def create_referral(self, referrer_merchant_id, referred_merchant_id, created_at, policy):
        record = ReferralRecord.objects.create(
            referrer_merchant_id=referrer_merchant_id,
            referred_merchant_id=referred_merchant_id,
            created_at=created_at,
            reward_percent=policy.reward_percent,
            reward_duration_days=policy.reward_duration_days,
        )
        return Referral(referrer_merchant_id, referred_merchant_id, record.reward_percent, record.reward_duration_days)

    def create_first_paid_period(self, merchant_id, paid_at, paid_amount_minor=None, currency=None):
        _, created = PaidPeriodRecord.objects.get_or_create(
            merchant_id=merchant_id,
            defaults={
                "paid_at": paid_at,
                "amount_minor": paid_amount_minor,
                "currency": currency,
            },
        )
        return created

    def referral_for_referred_merchant(self, merchant_id):
        record = ReferralRecord.objects.filter(referred_merchant_id=merchant_id).first()
        if record is None:
            return None
        return Referral(
            record.referrer_merchant_id,
            record.referred_merchant_id,
            record.reward_percent,
            record.reward_duration_days,
        )

    def mark_referral_rewarded(self, merchant_id, paid_at):
        referral = ReferralRecord.objects.select_for_update().filter(
            referred_merchant_id=merchant_id
        ).first()
        if referral is None or referral.rewarded_at is not None:
            return None
        referral.first_paid_at = paid_at
        referral.rewarded_at = paid_at
        referral.save(update_fields=["first_paid_at", "rewarded_at"])
        return Referral(
            referral.referrer_merchant_id,
            referral.referred_merchant_id,
            referral.reward_percent,
            referral.reward_duration_days,
        )
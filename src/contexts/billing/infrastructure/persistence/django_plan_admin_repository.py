from django.db import transaction

from ...application.ports.plan_admin_repository import (
    IPlanAdminRepository,
    PlanAdminRecord,
    PlanPriceAdminRecord,
)
from .models import (
    CouponRecord,
    PlanDefinitionRecord,
    PlanEntitlementRecord,
    PlanPriceRecord,
    OutboundRateRecord,
    ReferralPolicyRecord,
    TrialPolicyRecord,
)


class DjangoPlanAdminRepository(IPlanAdminRepository):
    """Persist admin plan changes atomically in Billing-owned tables."""

    @transaction.atomic
    def upsert_plan(self, code, is_active, display_order, entitlements):
        plan, _ = PlanDefinitionRecord.objects.update_or_create(
            code=code,
            defaults={"is_active": is_active, "display_order": display_order},
        )
        for key, value in entitlements.items():
            PlanEntitlementRecord.objects.update_or_create(
                plan=plan, key=key, defaults={"value": value}
            )
        return PlanAdminRecord(plan.code, plan.is_active, plan.display_order)

    def upsert_price(
        self, plan_code, country, currency, period_days, amount_minor, is_active
    ):
        plan = PlanDefinitionRecord.objects.filter(code=plan_code).first()
        if plan is None:
            return None
        price, _ = PlanPriceRecord.objects.update_or_create(
            plan=plan,
            country=country,
            currency=currency,
            period_days=period_days,
            defaults={"amount_minor": amount_minor, "is_active": is_active},
        )
        return PlanPriceAdminRecord(
            plan.code,
            price.country,
            price.currency,
            price.period_days,
            price.amount_minor,
            price.is_active,
        )

    @transaction.atomic
    def upsert_trial_policy(self, enabled, duration_days, target_plan_code, card_required):
        policy, _ = TrialPolicyRecord.objects.update_or_create(
            policy_key="default",
            defaults={
                "enabled": enabled,
                "duration_days": duration_days,
                "target_plan_code": target_plan_code,
                "card_required": card_required,
            },
        )
        return {
            "enabled": policy.enabled,
            "duration_days": policy.duration_days,
            "target_plan_code": policy.target_plan_code,
            "card_required": policy.card_required,
        }

    @transaction.atomic
    def upsert_referral_policy(self, reward_percent, reward_duration_days, max_referrals):
        policy, _ = ReferralPolicyRecord.objects.update_or_create(
            policy_key="default",
            defaults={
                "reward_percent": reward_percent,
                "reward_duration_days": reward_duration_days,
                "max_referrals_per_merchant": max_referrals,
            },
        )
        return {
            "reward_percent": policy.reward_percent,
            "reward_duration_days": policy.reward_duration_days,
            "max_referrals_per_merchant": policy.max_referrals_per_merchant,
        }

    @transaction.atomic
    def upsert_coupon(
        self, code, discount_percent, duration_days, max_redemptions,
        valid_from, valid_until, is_active,
    ):
        coupon, _ = CouponRecord.objects.update_or_create(
            code=code,
            defaults={
                "discount_percent": discount_percent,
                "duration_days": duration_days,
                "max_redemptions": max_redemptions,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "is_active": is_active,
            },
        )
        return {
            "code": coupon.code,
            "discount_percent": coupon.discount_percent,
            "duration_days": coupon.duration_days,
            "max_redemptions": coupon.max_redemptions,
            "valid_from": coupon.valid_from,
            "valid_until": coupon.valid_until,
            "is_active": coupon.is_active,
        }

    @transaction.atomic
    def upsert_outbound_rate(
        self, country, category, currency, amount_minor, valid_from, valid_until, is_active
    ):
        rate, _ = OutboundRateRecord.objects.update_or_create(
            country=country,
            category=category,
            currency=currency,
            valid_from=valid_from,
            defaults={
                "amount_minor": amount_minor,
                "valid_until": valid_until,
                "is_active": is_active,
            },
        )
        return {
            "country": rate.country,
            "category": rate.category,
            "currency": rate.currency,
            "amount_minor": rate.amount_minor,
            "valid_from": rate.valid_from,
            "valid_until": rate.valid_until,
            "is_active": rate.is_active,
        }
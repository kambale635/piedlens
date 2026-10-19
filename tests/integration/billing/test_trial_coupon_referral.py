from datetime import datetime, timedelta, timezone
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase

from contexts.billing.application.exceptions import (
    CouponAlreadyUsedException,
    ReferralAlreadyRedeemedException,
    TrialUnavailableException,
)
from contexts.billing.application.use_cases.apply_coupon_use_case import ApplyCouponUseCase
from contexts.billing.application.use_cases.record_first_paid_period_use_case import (
    RecordFirstPaidPeriodUseCase,
)
from contexts.billing.application.use_cases.redeem_referral_use_case import RedeemReferralUseCase
from contexts.billing.application.use_cases.start_trial_use_case import StartTrialUseCase
from contexts.billing.infrastructure.adapters.django_entitlement_reader import (
    DjangoEntitlementReader,
)
from contexts.billing.infrastructure.adapters.django_plan_catalog_reader import (
    DjangoPlanCatalogReader,
)
from contexts.billing.infrastructure.messaging.django_billing_outbox import DjangoBillingOutbox
from contexts.billing.infrastructure.persistence.django_billing_growth_repository import (
    DjangoBillingGrowthRepository,
)
from contexts.billing.infrastructure.persistence.django_billing_unit_of_work import (
    DjangoBillingUnitOfWork,
)
from contexts.billing.infrastructure.persistence.models import (
    CouponRecord,
    CouponRedemptionRecord,
    OutboxEventRecord,
    PaidPeriodRecord,
    ReferralRecord,
    TrialRecord,
)
from contexts.identity.infrastructure.persistence.models import MerchantRecord


class FixedClock:
    def __init__(self, instant):
        self.instant = instant

    def now(self):
        return self.instant


class BillingGrowthTests(TestCase):
    def setUp(self):
        call_command("seed_billing_plans", stdout=StringIO())
        self.now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
        self.clock = FixedClock(self.now)
        self.repository = DjangoBillingGrowthRepository()
        self.unit_of_work = DjangoBillingUnitOfWork()
        self.outbox = DjangoBillingOutbox()
        self.plan_catalog = DjangoPlanCatalogReader()

    def create_merchant(self, plan="discovery"):
        merchant_id = uuid4()
        MerchantRecord.objects.create(
            id=merchant_id,
            name="Test merchant",
            country="US",
            preferred_language="en",
            currency="USD",
            subscription_plan=plan,
            created_at=self.now,
        )
        return merchant_id

    def test_trial_activates_target_entitlements_then_falls_back_without_data_loss(self):
        merchant_id = self.create_merchant()
        start = StartTrialUseCase(
            self.repository, self.unit_of_work, self.plan_catalog, self.clock
        )
        result = start.execute(merchant_id)

        self.assertEqual(result.plan_code, "starter")
        self.assertEqual(result.ends_at - result.starts_at, timedelta(days=14))
        self.assertEqual(
            DjangoEntitlementReader(
                type("MerchantPlans", (), {"plan_for": lambda _self, _id: "discovery"})()
            ).entitlements_for(merchant_id)["max_segments"],
            3,
        )
        with self.assertRaises(TrialUnavailableException):
            start.execute(merchant_id)

        TrialRecord.objects.filter(merchant_id=merchant_id).update(ends_at=self.now)
        self.assertEqual(
            DjangoEntitlementReader(
                type("MerchantPlans", (), {"plan_for": lambda _self, _id: "discovery"})()
            ).entitlements_for(merchant_id)["max_segments"],
            0,
        )
        self.assertTrue(MerchantRecord.objects.filter(id=merchant_id).exists())

    def test_coupon_is_redeemed_once_and_event_is_outbox_atomic(self):
        merchant_id = self.create_merchant()
        CouponRecord.objects.create(
            code="WELCOME",
            discount_percent=20,
            duration_days=30,
            max_redemptions=1,
            valid_from=self.now - timedelta(days=1),
            valid_until=self.now + timedelta(days=1),
        )
        apply_coupon = ApplyCouponUseCase(
            self.repository, self.unit_of_work, self.outbox, self.clock
        )

        result = apply_coupon.execute(merchant_id, "welcome")

        self.assertEqual(result.discount_percent, 20)
        self.assertEqual(CouponRedemptionRecord.objects.count(), 1)
        self.assertEqual(OutboxEventRecord.objects.get().event_type, "CouponRedeemed")
        with self.assertRaises(CouponAlreadyUsedException):
            apply_coupon.execute(merchant_id, "WELCOME")

    def test_referral_reward_is_granted_only_once_after_first_paid_period(self):
        referrer_id = self.create_merchant("starter")
        referred_id = self.create_merchant()
        redeem = RedeemReferralUseCase(self.repository, self.unit_of_work, self.clock)
        redeem.execute(referred_id, referrer_id)

        pay = RecordFirstPaidPeriodUseCase(
            self.repository, self.unit_of_work, self.outbox
        )
        before_payment = ReferralRecord.objects.get(referred_merchant_id=referred_id)
        self.assertIsNone(before_payment.rewarded_at)
        first = pay.execute(referred_id, self.now)
        second = pay.execute(referred_id, self.now + timedelta(days=30))

        self.assertTrue(first.first_paid_period)
        self.assertTrue(first.referral_reward_granted)
        self.assertFalse(second.first_paid_period)
        self.assertFalse(second.referral_reward_granted)
        self.assertEqual(OutboxEventRecord.objects.filter(event_type="ReferralRewardGranted").count(), 1)
        self.assertEqual(PaidPeriodRecord.objects.filter(merchant_id=referred_id).count(), 1)
        with self.assertRaises(ReferralAlreadyRedeemedException):
            redeem.execute(referred_id, referrer_id)
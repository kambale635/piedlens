import uuid

from django.db import models


class PlanDefinitionRecord(models.Model):
    code = models.SlugField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField()

    class Meta:
        db_table = "billing_plan_definitions"
        ordering = ["display_order", "code"]


class PlanPriceRecord(models.Model):
    plan = models.ForeignKey(
        PlanDefinitionRecord, on_delete=models.CASCADE, related_name="prices"
    )
    country = models.CharField(max_length=2)
    currency = models.CharField(max_length=3)
    period_days = models.PositiveIntegerField()
    amount_minor = models.PositiveBigIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "billing_plan_prices"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "country", "currency", "period_days"],
                name="uniq_billing_plan_price_scope",
            )
        ]


class PlanEntitlementRecord(models.Model):
    plan = models.ForeignKey(
        PlanDefinitionRecord, on_delete=models.CASCADE, related_name="entitlements"
    )
    key = models.CharField(max_length=64)
    value = models.JSONField()

    class Meta:
        db_table = "billing_plan_entitlements"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "key"], name="uniq_billing_plan_entitlement"
            )
        ]


class TrialPolicyRecord(models.Model):
    policy_key = models.CharField(max_length=32, primary_key=True, default="default")
    enabled = models.BooleanField(default=True)
    duration_days = models.PositiveIntegerField(default=14)
    target_plan_code = models.CharField(max_length=32, default="starter")
    card_required = models.BooleanField(default=False)

    class Meta:
        db_table = "billing_trial_policies"


class TrialRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField(unique=True)
    target_plan_code = models.CharField(max_length=32)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(db_index=True)
    card_required = models.BooleanField()
    card_present = models.BooleanField()

    class Meta:
        db_table = "billing_trials"


class CouponRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    discount_percent = models.PositiveSmallIntegerField()
    duration_days = models.PositiveIntegerField()
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    redemption_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "billing_coupons"


class CouponRedemptionRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(
        CouponRecord, on_delete=models.PROTECT, related_name="redemptions"
    )
    merchant_id = models.UUIDField()
    redeemed_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    discount_percent = models.PositiveSmallIntegerField()
    duration_days = models.PositiveIntegerField()

    class Meta:
        db_table = "billing_coupon_redemptions"
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "merchant_id"], name="uniq_billing_coupon_per_merchant"
            )
        ]


class ReferralPolicyRecord(models.Model):
    policy_key = models.CharField(max_length=32, primary_key=True, default="default")
    reward_percent = models.PositiveSmallIntegerField(default=10)
    reward_duration_days = models.PositiveIntegerField(default=30)
    max_referrals_per_merchant = models.PositiveIntegerField(default=10)

    class Meta:
        db_table = "billing_referral_policies"


class ReferralRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer_merchant_id = models.UUIDField(db_index=True)
    referred_merchant_id = models.UUIDField(unique=True)
    created_at = models.DateTimeField()
    first_paid_at = models.DateTimeField(null=True, blank=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)
    reward_percent = models.PositiveSmallIntegerField()
    reward_duration_days = models.PositiveIntegerField()

    class Meta:
        db_table = "billing_referrals"


class PaidPeriodRecord(models.Model):
    merchant_id = models.UUIDField(unique=True)
    paid_at = models.DateTimeField()

    class Meta:
        db_table = "billing_paid_periods"


class BillingMerchantLockRecord(models.Model):
    merchant_id = models.UUIDField(primary_key=True)

    class Meta:
        db_table = "billing_merchant_locks"


class OutboxEventRecord(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="billing")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "billing_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]


class OutboundRateRecord(models.Model):
    country = models.CharField(max_length=2)
    category = models.CharField(max_length=24)
    currency = models.CharField(max_length=3)
    amount_minor = models.PositiveBigIntegerField()
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "billing_outbound_rates"
        constraints = [
            models.UniqueConstraint(
                fields=["country", "category", "currency", "valid_from"],
                name="uniq_billing_outbound_rate_period",
            )
        ]
        indexes = [models.Index(fields=["country", "category", "is_active"])]


class OutboundMessageUsageRecord(models.Model):
    merchant_id = models.UUIDField()
    month = models.DateField()
    category = models.CharField(max_length=24)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "billing_outbound_message_usage"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant_id", "month", "category"],
                name="uniq_billing_outbound_usage_month_category",
            )
        ]
        indexes = [models.Index(fields=["merchant_id", "month"])]


class OutboundMessageReservationRecord(models.Model):
    idempotency_key = models.CharField(max_length=160, primary_key=True)
    merchant_id = models.UUIDField()
    month = models.DateField()
    category = models.CharField(max_length=24)

    class Meta:
        db_table = "billing_outbound_message_reservations"
        indexes = [models.Index(fields=["merchant_id", "month"])]

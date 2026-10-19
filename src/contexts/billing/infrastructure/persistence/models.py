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

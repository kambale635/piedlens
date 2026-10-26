from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contexts.billing.infrastructure.persistence.models import (
    PlanDefinitionRecord,
    PlanEntitlementRecord,
    PlanPriceRecord,
    ReferralPolicyRecord,
    TrialPolicyRecord,
)


PLAN_SEED = {
    "discovery": {
        "order": 0,
        "prices": (),
        "entitlements": {
            "max_connections": 1,
            "sync_mode": "hourly",
            "history_days": 7,
            "dormant_money_detail": False,
            "reminder_modes": [],
            "outbound_monthly_cap": 0,
            "max_segments": 0,
            "bulk_messages": False,
            "max_managed_merchants": 0,
            "manual_import": True,
            "export_enabled": True,
        },
    },
    "starter": {
        "order": 1,
        "prices": ((7, 60), (30, 200), (365, 2000)),
        "entitlements": {
            "max_connections": 1,
            "sync_mode": "hourly",
            "history_days": 90,
            "dormant_money_detail": True,
            "reminder_modes": ["manual_link"],
            "outbound_monthly_cap": 0,
            "max_segments": 3,
            "bulk_messages": False,
            "max_managed_merchants": 0,
            "manual_import": True,
            "export_enabled": True,
        },
    },
    "pro": {
        "order": 2,
        "prices": ((7, 150), (30, 500), (365, 5000)),
        "entitlements": {
            "max_connections": 3,
            "sync_mode": "realtime",
            "history_days": 365,
            "dormant_money_detail": True,
            "reminder_modes": ["manual_link", "api_send"],
            "outbound_monthly_cap": 200,
            "max_segments": -1,
            "bulk_messages": True,
            "max_managed_merchants": 0,
            "manual_import": True,
            "export_enabled": True,
        },
    },
    "agency": {
        "order": 3,
        "prices": ((30, 1500), (365, 15000)),
        "entitlements": {
            "max_connections": -1,
            "sync_mode": "realtime",
            "history_days": 730,
            "dormant_money_detail": True,
            "reminder_modes": ["manual_link", "api_send"],
            "outbound_monthly_cap": 1000,
            "max_segments": -1,
            "bulk_messages": True,
            "max_managed_merchants": 20,
            "manual_import": True,
            "export_enabled": True,
        },
    },
}


class Command(BaseCommand):
    help = "Seed provisional Billing plans without overwriting administrator changes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite seeded plan fields, prices, and entitlements with provisional defaults.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        self._validate_existing_data()
        with transaction.atomic():
            trial_policy, trial_created = TrialPolicyRecord.objects.get_or_create(
                policy_key="default",
                defaults={
                    "enabled": True,
                    "duration_days": 14,
                    "target_plan_code": "starter",
                    "card_required": False,
                },
            )
            referral_policy, referral_created = ReferralPolicyRecord.objects.get_or_create(
                policy_key="default",
                defaults={
                    "reward_percent": 10,
                    "reward_duration_days": 30,
                    "max_referrals_per_merchant": 10,
                },
            )
            if force and not trial_created:
                trial_policy.enabled = True
                trial_policy.duration_days = 14
                trial_policy.target_plan_code = "starter"
                trial_policy.card_required = False
                trial_policy.save()
            if force and not referral_created:
                referral_policy.reward_percent = 10
                referral_policy.reward_duration_days = 30
                referral_policy.max_referrals_per_merchant = 10
                referral_policy.save()
            for code, data in PLAN_SEED.items():
                plan, created = PlanDefinitionRecord.objects.get_or_create(
                    code=code,
                    defaults={"is_active": True, "display_order": data["order"]},
                )
                if force and not created:
                    plan.is_active = True
                    plan.display_order = data["order"]
                    plan.save(update_fields=["is_active", "display_order"])
                for period_days, amount_minor in data["prices"]:
                    price, price_created = PlanPriceRecord.objects.get_or_create(
                        plan=plan,
                        country="*",
                        currency="USD",
                        period_days=period_days,
                        defaults={"amount_minor": amount_minor, "is_active": True},
                    )
                    if force and not price_created:
                        price.amount_minor = amount_minor
                        price.is_active = True
                        price.save(update_fields=["amount_minor", "is_active"])
                for key, value in data["entitlements"].items():
                    entitlement, entitlement_created = PlanEntitlementRecord.objects.get_or_create(
                        plan=plan, key=key, defaults={"value": value}
                    )
                    if force and not entitlement_created and entitlement.value != value:
                        entitlement.value = value
                        entitlement.save(update_fields=["value"])
        self.stdout.write(self.style.SUCCESS("Billing plans seeded."))

    @staticmethod
    def _validate_existing_data():
        known_keys = {
            key
            for plan in PLAN_SEED.values()
            for key in plan["entitlements"]
        }
        if PlanEntitlementRecord.objects.exclude(key__in=known_keys).exists():
            raise CommandError("Billing catalog contains an unknown entitlement key.")
        for entitlement in PlanEntitlementRecord.objects.select_related("plan"):
            if not _valid_entitlement_value(entitlement.key, entitlement.value):
                raise CommandError("Billing catalog contains an invalid entitlement value.")
            if entitlement.key == "export_enabled" and entitlement.value is not True:
                raise CommandError("Billing catalog must allow data exports on every plan.")
        for price in PlanPriceRecord.objects.select_related("plan"):
            if price.country != "*" and len(price.country) != 2:
                raise CommandError("Billing price has an invalid country code.")
            if len(price.currency) != 3 or price.period_days < 1:
                raise CommandError("Billing price has an invalid currency or period.")


def _valid_entitlement_value(key, value):
    if key in {"max_connections", "history_days", "outbound_monthly_cap", "max_segments", "max_managed_merchants"}:
        return isinstance(value, int) and not isinstance(value, bool) and value >= -1
    if key in {"dormant_money_detail", "bulk_messages", "manual_import", "export_enabled"}:
        return isinstance(value, bool)
    if key == "sync_mode":
        return isinstance(value, str) and bool(value)
    if key == "reminder_modes":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return False
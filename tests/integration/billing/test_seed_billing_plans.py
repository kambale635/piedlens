from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from contexts.billing.infrastructure.persistence.models import (
    PlanDefinitionRecord,
    PlanEntitlementRecord,
    PlanPriceRecord,
)


class SeedBillingPlansTests(TestCase):
    def test_seed_is_idempotent_and_preserves_admin_changes_until_force(self):
        call_command("seed_billing_plans", stdout=StringIO())
        call_command("seed_billing_plans", stdout=StringIO())
        starter = PlanDefinitionRecord.objects.get(code="starter")
        price = PlanPriceRecord.objects.get(
            plan=starter, country="*", currency="USD", period_days=30
        )
        entitlement = PlanEntitlementRecord.objects.get(
            plan=starter, key="max_segments"
        )
        price.amount_minor = 250
        price.save(update_fields=["amount_minor"])
        entitlement.value = 8
        entitlement.save(update_fields=["value"])

        call_command("seed_billing_plans", stdout=StringIO())
        price.refresh_from_db()
        entitlement.refresh_from_db()
        self.assertEqual(price.amount_minor, 250)
        self.assertEqual(entitlement.value, 8)
        self.assertEqual(PlanDefinitionRecord.objects.count(), 4)

        call_command("seed_billing_plans", "--force", stdout=StringIO())
        price.refresh_from_db()
        entitlement.refresh_from_db()
        self.assertEqual(price.amount_minor, 200)
        self.assertEqual(entitlement.value, 3)

    def test_seed_rejects_incoherent_entitlement_data(self):
        plan = PlanDefinitionRecord.objects.create(code="custom", display_order=10)
        PlanEntitlementRecord.objects.create(
            plan=plan, key="max_connections", value="unlimited"
        )

        with self.assertRaises(CommandError):
            call_command("seed_billing_plans", stdout=StringIO())

    def test_seed_rejects_disabled_exports(self):
        plan = PlanDefinitionRecord.objects.create(code="custom", display_order=10)
        PlanEntitlementRecord.objects.create(
            plan=plan, key="export_enabled", value=False
        )

        with self.assertRaises(CommandError):
            call_command("seed_billing_plans", stdout=StringIO())

    def test_seed_creates_provisional_price_and_entitlement_catalog(self):
        call_command("seed_billing_plans", stdout=StringIO())
        self.assertEqual(
            list(
                PlanPriceRecord.objects.filter(plan__code="pro")
                .order_by("period_days")
                .values_list("country", "currency", "period_days", "amount_minor")
            ),
            [("*", "USD", 7, 150), ("*", "USD", 30, 500), ("*", "USD", 365, 5000)],
        )
        self.assertFalse(PlanPriceRecord.objects.filter(plan__code="discovery").exists())
        self.assertEqual(
            PlanEntitlementRecord.objects.filter(plan__code="agency").count(), 10
        )
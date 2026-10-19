from uuid import uuid4

from django.test import TestCase

from contexts.billing.infrastructure.adapters.django_entitlement_reader import (
    DjangoEntitlementReader,
)
from contexts.billing.infrastructure.persistence.models import (
    PlanDefinitionRecord,
    PlanEntitlementRecord,
)


class MerchantPlanStub:
    def __init__(self, plan_code):
        self.plan_code = plan_code

    def plan_for(self, merchant_id):
        return self.plan_code


class DjangoEntitlementReaderTests(TestCase):
    def test_reads_entitlements_for_active_merchant_plan(self):
        plan = PlanDefinitionRecord.objects.create(code="starter", display_order=1)
        PlanEntitlementRecord.objects.create(
            plan=plan, key="max_connections", value=1
        )
        PlanEntitlementRecord.objects.create(
            plan=plan, key="sync_mode", value="hourly"
        )
        reader = DjangoEntitlementReader(MerchantPlanStub("starter"))

        self.assertEqual(
            reader.entitlements_for(uuid4()),
            {"max_connections": 1, "sync_mode": "hourly"},
        )

    def test_returns_empty_entitlements_for_unknown_or_inactive_plan(self):
        PlanDefinitionRecord.objects.create(
            code="inactive", display_order=1, is_active=False
        )

        self.assertEqual(
            DjangoEntitlementReader(MerchantPlanStub("missing")).entitlements_for(
                uuid4()
            ),
            {},
        )
        self.assertEqual(
            DjangoEntitlementReader(MerchantPlanStub("inactive")).entitlements_for(
                uuid4()
            ),
            {},
        )
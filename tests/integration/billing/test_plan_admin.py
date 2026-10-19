from django.test import TestCase

from contexts.billing.application.use_cases.upsert_plan_use_case import (
    InvalidPlanDefinitionException,
    UpsertPlanUseCase,
)
from contexts.billing.infrastructure.persistence.django_plan_admin_repository import (
    DjangoPlanAdminRepository,
)
from contexts.billing.infrastructure.persistence.models import (
    PlanDefinitionRecord,
    PlanEntitlementRecord,
)


class PlanAdminTests(TestCase):
    def test_upsert_preserves_omitted_entitlements(self):
        plan = PlanDefinitionRecord.objects.create(code="custom", display_order=1)
        PlanEntitlementRecord.objects.create(
            plan=plan, key="max_connections", value=4
        )

        UpsertPlanUseCase(DjangoPlanAdminRepository()).execute(
            code="custom",
            is_active=True,
            display_order=2,
            entitlements={"history_days": 45},
        )

        values = dict(
            PlanEntitlementRecord.objects.filter(plan=plan).values_list("key", "value")
        )
        self.assertEqual(values, {"max_connections": 4, "history_days": 45})

    def test_admin_cannot_disable_data_exports(self):
        use_case = UpsertPlanUseCase(DjangoPlanAdminRepository())

        with self.assertRaises(InvalidPlanDefinitionException):
            use_case.execute(
                code="custom",
                is_active=True,
                display_order=1,
                entitlements={"export_enabled": False},
            )

        self.assertFalse(PlanDefinitionRecord.objects.filter(code="custom").exists())
from shared_kernel.ports import IPlanCatalogReader

from ..persistence.models import PlanDefinitionRecord


class DjangoPlanCatalogReader(IPlanCatalogReader):
    """Expose active plan-code validation without leaking Billing persistence."""

    def is_active_plan(self, plan_code: str) -> bool:
        return PlanDefinitionRecord.objects.filter(
            code=plan_code, is_active=True
        ).exists()

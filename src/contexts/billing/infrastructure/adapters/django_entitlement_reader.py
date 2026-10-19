from uuid import UUID

from django.utils import timezone

from shared_kernel.ports import IEntitlementReader, IMerchantPlanReader

from ..persistence.models import PlanDefinitionRecord, TrialRecord


class DjangoEntitlementReader(IEntitlementReader):
    """Expose active plan entitlements through the shared-kernel port."""

    def __init__(self, merchant_plans: IMerchantPlanReader) -> None:
        self._merchant_plans = merchant_plans

    def entitlements_for(self, merchant_id: UUID) -> dict[str, object]:
        active_trial = TrialRecord.objects.filter(
            merchant_id=merchant_id,
            starts_at__lte=timezone.now(),
            ends_at__gt=timezone.now(),
        ).first()
        if active_trial is not None:
            return self.entitlements_for_plan(active_trial.target_plan_code)
        plan_code = self._merchant_plans.plan_for(merchant_id)
        if plan_code is None:
            return {}
        return self.entitlements_for_plan(plan_code)

    def entitlements_for_plan(self, plan_code: str) -> dict[str, object]:
        plan = PlanDefinitionRecord.objects.filter(
            code=plan_code, is_active=True
        ).first()
        if plan is None:
            return {}
        return dict(plan.entitlements.values_list("key", "value"))

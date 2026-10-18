from uuid import UUID

from shared_kernel.ports import IMerchantPlanReader

from ..persistence.models import MerchantRecord


class DjangoMerchantPlanReader(IMerchantPlanReader):
    """Expose the merchant's plan code through the shared-kernel read port."""

    def plan_for(self, merchant_id: UUID) -> str | None:
        return MerchantRecord.objects.filter(id=merchant_id).values_list(
            "subscription_plan", flat=True
        ).first()
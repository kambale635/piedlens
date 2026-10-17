from uuid import UUID

from contexts.identity.domain.value_objects.identity_values import SubscriptionPlan
from contexts.identity.infrastructure.persistence.models import MerchantRecord


class DjangoConnectionPlanReader:
    """Implement the shared plan-capacity query from Identity-owned Merchant data."""

    def active_connection_limit(self, merchant_id: UUID) -> int | None:
        """Return the configured plan capacity; unknown merchants cannot connect."""
        plan_name = MerchantRecord.objects.filter(id=merchant_id).values_list(
            "subscription_plan", flat=True
        ).first()
        if plan_name is None:
            return 0
        return SubscriptionPlan(plan_name).active_connection_limit
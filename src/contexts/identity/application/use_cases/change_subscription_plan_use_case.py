from datetime import timezone
from uuid import UUID

from ...domain.entities.merchant import Merchant
from ...domain.events.identity_events import MerchantPlanChanged
from ...domain.value_objects.identity_values import SubscriptionPlan
from ..exceptions.identity_exceptions import InvalidMerchantData, MerchantNotFound
from ..ports.identity_ports import (
    IIdentityClock,
    IIdentityOutbox,
    IIdentityUnitOfWork,
    IMerchantRepository,
)
from shared_kernel.ports import IConnectionUsageReader


class ChangeSubscriptionPlanUseCase:
    """Apply a confirmed subscription plan without exceeding current usage (INV-ID-03)."""

    def __init__(self, merchants: IMerchantRepository, usage: IConnectionUsageReader,
                 unit_of_work: IIdentityUnitOfWork, outbox: IIdentityOutbox,
                 clock: IIdentityClock) -> None:
        self.merchants = merchants
        self.usage = usage
        self.unit_of_work = unit_of_work
        self.outbox = outbox
        self.clock = clock

    def execute(self, merchant_id: UUID, new_plan: str) -> dict:
        """Change one Merchant aggregate after payment confirmation (INV-ID-03)."""
        merchant = self.merchants.find_by_id(merchant_id)
        if merchant is None:
            raise MerchantNotFound()
        try:
            plan = SubscriptionPlan(new_plan)
        except ValueError as error:
            raise InvalidMerchantData() from error
        updated = merchant.change_plan(
            plan, self.usage.count_active_connections(merchant_id)
        )
        effective_at = self.clock.now_utc().astimezone(timezone.utc)
        with self.unit_of_work:
            self.merchants.save(updated)
            self.outbox.add(MerchantPlanChanged(merchant.id, plan.value, effective_at))
        return {
            "merchantId": merchant.id,
            "subscriptionPlan": plan.value,
            "effectiveAt": effective_at,
        }
from datetime import timezone
from uuid import UUID

from ...domain.entities.merchant import Merchant
from ...domain.events.identity_events import MerchantPlanChanged
from ..exceptions.identity_exceptions import InvalidMerchantData, MerchantNotFound
from ..ports.identity_ports import (
    IIdentityClock,
    IIdentityOutbox,
    IIdentityUnitOfWork,
    IMerchantRepository,
)
from shared_kernel.ports import IConnectionUsageReader, IEntitlementReader, IPlanCatalogReader


class ChangeSubscriptionPlanUseCase:
    """Apply a confirmed subscription plan without exceeding current usage (INV-ID-03)."""

    def __init__(self, merchants: IMerchantRepository, usage: IConnectionUsageReader,
                 plan_catalog: IPlanCatalogReader, entitlements: IEntitlementReader,
                 unit_of_work: IIdentityUnitOfWork, outbox: IIdentityOutbox,
                 clock: IIdentityClock) -> None:
        self.merchants = merchants
        self.usage = usage
        self.plan_catalog = plan_catalog
        self.entitlements = entitlements
        self.unit_of_work = unit_of_work
        self.outbox = outbox
        self.clock = clock

    def execute(self, merchant_id: UUID, new_plan: str) -> dict:
        """Change one Merchant aggregate after payment confirmation (INV-ID-03)."""
        with self.unit_of_work:
            return self.change_in_current_transaction(merchant_id, new_plan)

    def change_in_current_transaction(self, merchant_id: UUID, new_plan: str) -> dict:
        """Apply the same validated Merchant transition inside a caller-owned consumer transaction (INV-ID-03/INV-TR-01/02/03)."""
        merchant = self.merchants.find_by_id(merchant_id)
        if merchant is None:
            raise MerchantNotFound()
        if not self.plan_catalog.is_active_plan(new_plan):
            raise InvalidMerchantData()
        raw_limit = self.entitlements.entitlements_for_plan(new_plan).get(
            "max_connections",
            None,
        )
        if not isinstance(raw_limit, int) or isinstance(raw_limit, bool) or raw_limit < -1:
            raise InvalidMerchantData()
        limit = None if raw_limit == -1 else raw_limit
        updated = merchant.change_plan(
            new_plan, self.usage.count_active_connections(merchant_id), limit
        )
        effective_at = self.clock.now_utc().astimezone(timezone.utc)
        self.merchants.save(updated)
        self.outbox.add(MerchantPlanChanged(merchant.id, new_plan, effective_at))
        return {
            "merchantId": merchant.id,
            "subscriptionPlan": new_plan,
            "effectiveAt": effective_at,
        }
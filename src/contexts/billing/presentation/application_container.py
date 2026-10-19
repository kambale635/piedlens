from contexts.billing.application.use_cases.upsert_plan_price_use_case import (
    UpsertPlanPriceUseCase,
)
from contexts.billing.application.use_cases.upsert_plan_use_case import UpsertPlanUseCase
from contexts.billing.application.use_cases.list_pricing_use_case import ListPricingUseCase
from contexts.billing.infrastructure.adapters.django_plan_pricing_reader import (
    DjangoPlanPricingReader,
)
from contexts.billing.infrastructure.persistence.django_plan_admin_repository import (
    DjangoPlanAdminRepository,
)


class BillingContainer:
    """Composition root for Billing presentation use cases."""

    @staticmethod
    def upsert_plan() -> UpsertPlanUseCase:
        return UpsertPlanUseCase(DjangoPlanAdminRepository())

    @staticmethod
    def upsert_plan_price() -> UpsertPlanPriceUseCase:
        return UpsertPlanPriceUseCase(DjangoPlanAdminRepository())

    @staticmethod
    def list_pricing() -> ListPricingUseCase:
        return ListPricingUseCase(DjangoPlanPricingReader())
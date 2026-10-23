from contexts.billing.application.use_cases.upsert_plan_price_use_case import (
    UpsertPlanPriceUseCase,
)
from contexts.billing.application.use_cases.upsert_plan_use_case import UpsertPlanUseCase
from contexts.billing.application.use_cases.start_trial_use_case import StartTrialUseCase
from contexts.billing.application.use_cases.apply_coupon_use_case import ApplyCouponUseCase
from contexts.billing.application.use_cases.redeem_referral_use_case import RedeemReferralUseCase
from contexts.billing.application.use_cases.record_first_paid_period_use_case import (
    RecordFirstPaidPeriodUseCase,
)
from contexts.billing.application.use_cases.upsert_growth_policy_use_cases import (
    UpsertReferralPolicyUseCase,
    UpsertTrialPolicyUseCase,
)
from contexts.billing.application.use_cases.upsert_coupon_use_case import UpsertCouponUseCase
from contexts.billing.application.use_cases.estimate_outbound_cost_use_case import (
    EstimateOutboundCostUseCase,
)
from contexts.billing.application.use_cases.generate_value_report_use_case import (
    GenerateValueReportUseCase,
)
from contexts.billing.application.use_cases.upsert_outbound_rate_use_case import (
    UpsertOutboundRateUseCase,
)
from contexts.billing.infrastructure.adapters.django_plan_catalog_reader import (
    DjangoPlanCatalogReader,
)
from contexts.billing.infrastructure.adapters.system_billing_clock import SystemBillingClock
from contexts.billing.infrastructure.messaging.django_billing_outbox import DjangoBillingOutbox
from contexts.billing.infrastructure.persistence.django_billing_growth_repository import (
    DjangoBillingGrowthRepository,
)
from contexts.billing.infrastructure.persistence.django_billing_unit_of_work import (
    DjangoBillingUnitOfWork,
)
from contexts.billing.application.use_cases.list_pricing_use_case import ListPricingUseCase
from contexts.billing.infrastructure.adapters.django_plan_pricing_reader import (
    DjangoPlanPricingReader,
)
from contexts.billing.infrastructure.adapters.django_outbound_services import (
    DjangoMerchantOutboundUsageReader,
    DjangoOutboundCostEstimator,
    DjangoOutboundUsageRecorder,
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

    @staticmethod
    def start_trial() -> StartTrialUseCase:
        return StartTrialUseCase(
            DjangoBillingGrowthRepository(),
            DjangoBillingUnitOfWork(),
            DjangoPlanCatalogReader(),
            SystemBillingClock(),
        )

    @staticmethod
    def apply_coupon() -> ApplyCouponUseCase:
        return ApplyCouponUseCase(
            DjangoBillingGrowthRepository(),
            DjangoBillingUnitOfWork(),
            DjangoBillingOutbox(),
            SystemBillingClock(),
        )

    @staticmethod
    def redeem_referral() -> RedeemReferralUseCase:
        return RedeemReferralUseCase(
            DjangoBillingGrowthRepository(), DjangoBillingUnitOfWork(), SystemBillingClock()
        )

    @staticmethod
    def record_first_paid_period() -> RecordFirstPaidPeriodUseCase:
        return RecordFirstPaidPeriodUseCase(
            DjangoBillingGrowthRepository(),
            DjangoBillingUnitOfWork(),
            DjangoBillingOutbox(),
        )

    @staticmethod
    def upsert_trial_policy() -> UpsertTrialPolicyUseCase:
        return UpsertTrialPolicyUseCase(
            DjangoPlanAdminRepository(), DjangoPlanCatalogReader()
        )

    @staticmethod
    def upsert_referral_policy() -> UpsertReferralPolicyUseCase:
        return UpsertReferralPolicyUseCase(DjangoPlanAdminRepository())

    @staticmethod
    def upsert_coupon() -> UpsertCouponUseCase:
        return UpsertCouponUseCase(DjangoPlanAdminRepository())

    @staticmethod
    def estimate_outbound_cost(
        merchant_country_reader, merchant_currency_reader
    ) -> EstimateOutboundCostUseCase:
        return EstimateOutboundCostUseCase(
            merchant_country_reader, merchant_currency_reader, DjangoOutboundCostEstimator()
        )

    @staticmethod
    def upsert_outbound_rate() -> UpsertOutboundRateUseCase:
        return UpsertOutboundRateUseCase(DjangoPlanAdminRepository())

    @staticmethod
    def generate_value_report(
        merchant_country_reader,
        merchant_currency_reader,
    ) -> GenerateValueReportUseCase:
        return GenerateValueReportUseCase(
            merchant_country_reader,
            merchant_currency_reader,
            DjangoMerchantOutboundUsageReader(),
            DjangoOutboundCostEstimator(),
        )

    @staticmethod
    def outbound_usage_recorder() -> DjangoOutboundUsageRecorder:
        return DjangoOutboundUsageRecorder(DjangoEntitlementReader(DjangoMerchantPlanReader()))

    @staticmethod
    def outbound_usage_reader() -> DjangoMerchantOutboundUsageReader:
        return DjangoMerchantOutboundUsageReader()
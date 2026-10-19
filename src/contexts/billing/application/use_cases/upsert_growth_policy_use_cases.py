from shared_kernel.application_exceptions import ValidationException
from shared_kernel.ports import IPlanCatalogReader

from ..ports.growth_admin_repository import IBillingGrowthAdminRepository


class InvalidGrowthPolicyException(ValidationException):
    error_code = "INVALID_BILLING_POLICY"


class UpsertTrialPolicyUseCase:
    """Update configurable trial duration, plan, and card requirement."""

    def __init__(self, repository: IBillingGrowthAdminRepository, plan_catalog: IPlanCatalogReader):
        self._repository = repository
        self._plan_catalog = plan_catalog

    def execute(self, enabled, duration_days, target_plan_code, card_required):
        if (
            not isinstance(enabled, bool)
            or not isinstance(card_required, bool)
            or not isinstance(duration_days, int)
            or isinstance(duration_days, bool)
            or duration_days < 1
        ):
            raise InvalidGrowthPolicyException()
        if not self._plan_catalog.is_active_plan(target_plan_code):
            raise InvalidGrowthPolicyException()
        return self._repository.upsert_trial_policy(
            enabled, duration_days, target_plan_code, card_required
        )


class UpsertReferralPolicyUseCase:
    """Update referral reward and per-referrer usage limits."""

    def __init__(self, repository: IBillingGrowthAdminRepository):
        self._repository = repository

    def execute(self, reward_percent, reward_duration_days, max_referrals):
        if (
            not isinstance(reward_percent, int)
            or isinstance(reward_percent, bool)
            or not 1 <= reward_percent <= 100
            or not isinstance(reward_duration_days, int)
            or isinstance(reward_duration_days, bool)
            or reward_duration_days < 1
            or not isinstance(max_referrals, int)
            or isinstance(max_referrals, bool)
            or max_referrals < 0
        ):
            raise InvalidGrowthPolicyException()
        return self._repository.upsert_referral_policy(
            reward_percent, reward_duration_days, max_referrals
        )
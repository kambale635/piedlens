from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from shared_kernel.ports import IPlanCatalogReader

from ..exceptions import (
    TrialCardRequiredException,
    TrialUnavailableException,
)
from ..ports.growth_repository import IBillingGrowthRepository, IBillingUnitOfWork


@dataclass(frozen=True)
class StartTrialResult:
    merchant_id: UUID
    plan_code: str
    starts_at: datetime
    ends_at: datetime


class StartTrialUseCase:
    """Start the single configured trial for a merchant (INV-BILL-01)."""

    def __init__(self, repository, unit_of_work, plan_catalog, clock) -> None:
        self._repository: IBillingGrowthRepository = repository
        self._unit_of_work: IBillingUnitOfWork = unit_of_work
        self._plan_catalog: IPlanCatalogReader = plan_catalog
        self._clock = clock

    def execute(self, merchant_id: UUID, card_provided: bool = False) -> StartTrialResult:
        """Start a trial once; expiration falls back to Discovery without deleting merchant data."""
        policy = self._repository.trial_policy()
        if not policy.enabled or policy.duration_days < 1:
            raise TrialUnavailableException("Trial policy is unavailable.")
        if policy.card_required and not card_provided:
            raise TrialCardRequiredException("A payment card is required for this trial.")
        if not self._plan_catalog.is_active_plan(policy.target_plan_code):
            raise TrialUnavailableException("Trial target plan is not active.")
        starts_at = self._clock.now()
        ends_at = starts_at + timedelta(days=policy.duration_days)
        with self._unit_of_work:
            self._repository.lock_merchant(merchant_id)
            if self._repository.has_ever_started_trial(merchant_id):
                raise TrialUnavailableException("A merchant can start only one trial.")
            self._repository.create_trial(
                merchant_id,
                policy.target_plan_code,
                starts_at,
                ends_at,
                policy.card_required,
                card_provided,
            )
        return StartTrialResult(merchant_id, policy.target_plan_code, starts_at, ends_at)
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.events import ReferralRewardGranted
from ..ports.growth_repository import IBillingGrowthRepository, IBillingOutbox, IBillingUnitOfWork


@dataclass(frozen=True)
class RecordFirstPaidPeriodResult:
    merchant_id: UUID
    first_paid_period: bool
    referral_reward_granted: bool


class RecordFirstPaidPeriodUseCase:
    """Grant a referral reward once, only after the referred merchant's first paid period (INV-BILL-03)."""

    def __init__(self, repository, unit_of_work, outbox) -> None:
        self._repository: IBillingGrowthRepository = repository
        self._unit_of_work: IBillingUnitOfWork = unit_of_work
        self._outbox: IBillingOutbox = outbox

    def execute(self, merchant_id: UUID, paid_at: datetime) -> RecordFirstPaidPeriodResult:
        """Record payment and reward event atomically; duplicate payment notifications have no second effect."""
        granted = False
        with self._unit_of_work:
            self._repository.lock_merchant(merchant_id)
            first_paid_period = self._repository.create_first_paid_period(merchant_id, paid_at)
            if first_paid_period:
                referral = self._repository.mark_referral_rewarded(merchant_id, paid_at)
                if referral is not None:
                    self._outbox.add(ReferralRewardGranted.create(referral, paid_at))
                    granted = True
        return RecordFirstPaidPeriodResult(merchant_id, first_paid_period, granted)
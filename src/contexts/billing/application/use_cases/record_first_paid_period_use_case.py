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

    def execute(
        self,
        merchant_id: UUID,
        paid_at: datetime,
        paid_amount_minor: int | None = None,
        currency: str | None = None,
    ) -> RecordFirstPaidPeriodResult:
        """Record payment and reward event atomically; duplicate payment notifications have no second effect."""
        if paid_amount_minor is not None and (
            not isinstance(paid_amount_minor, int)
            or isinstance(paid_amount_minor, bool)
            or paid_amount_minor < 0
            or not currency
            or len(currency) != 3
            or not currency.isalpha()
        ):
            raise ValueError("Actual paid amount requires non-negative minor units and an ISO currency.")
        granted = False
        with self._unit_of_work:
            self._repository.lock_merchant(merchant_id)
            first_paid_period = self._repository.create_first_paid_period(
                merchant_id, paid_at, paid_amount_minor, currency.upper() if currency else None
            )
            if first_paid_period:
                referral = self._repository.mark_referral_rewarded(merchant_id, paid_at)
                if referral is not None:
                    self._outbox.add(ReferralRewardGranted.create(referral, paid_at))
                    granted = True
        return RecordFirstPaidPeriodResult(merchant_id, first_paid_period, granted)
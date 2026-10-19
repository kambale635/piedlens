from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..exceptions import (
    ReferralAlreadyRedeemedException,
    ReferralLimitReachedException,
    ReferralNotValidException,
)
from ..ports.growth_repository import IBillingGrowthRepository, IBillingUnitOfWork


@dataclass(frozen=True)
class RedeemReferralResult:
    referrer_merchant_id: UUID
    referred_merchant_id: UUID
    reward_percent: int
    reward_duration_days: int


class RedeemReferralUseCase:
    """Register one valid referral without granting its reward before payment (INV-BILL-03)."""

    def __init__(self, repository, unit_of_work, clock) -> None:
        self._repository: IBillingGrowthRepository = repository
        self._unit_of_work: IBillingUnitOfWork = unit_of_work
        self._clock = clock

    def execute(self, referred_merchant_id: UUID, referrer_merchant_id: UUID) -> RedeemReferralResult:
        """Reject self-referrals, duplicate referred merchants, and referrers over their configured cap."""
        if referred_merchant_id == referrer_merchant_id:
            raise ReferralNotValidException("Self-referral is not allowed.")
        policy = self._repository.referral_policy()
        if policy.reward_percent < 1 or policy.reward_percent > 100 or policy.reward_duration_days < 1:
            raise ReferralNotValidException("Referral reward policy is invalid.")
        with self._unit_of_work:
            for locked_merchant_id in sorted(
                (referrer_merchant_id, referred_merchant_id), key=str
            ):
                self._repository.lock_merchant(locked_merchant_id)
            if self._repository.referral_exists_for_merchant(referred_merchant_id):
                raise ReferralAlreadyRedeemedException("Merchant already redeemed a referral.")
            if self._repository.count_referrals(referrer_merchant_id) >= policy.max_referrals_per_merchant:
                raise ReferralLimitReachedException("Referrer reached the configured referral limit.")
            referral = self._repository.create_referral(
                referrer_merchant_id, referred_merchant_id, self._clock.now(), policy
            )
        return RedeemReferralResult(
            referral.referrer_merchant_id,
            referral.referred_merchant_id,
            referral.reward_percent,
            referral.reward_duration_days,
        )
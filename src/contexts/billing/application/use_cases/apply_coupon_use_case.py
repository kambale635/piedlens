from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from ...domain.events import CouponRedeemed
from ..exceptions import (
    CouponAlreadyUsedException,
    CouponNotFoundException,
    CouponNotValidException,
)
from ..ports.growth_repository import IBillingGrowthRepository, IBillingOutbox, IBillingUnitOfWork


@dataclass(frozen=True)
class ApplyCouponResult:
    coupon_code: str
    discount_percent: int
    redeemed_at: datetime
    expires_at: datetime


class ApplyCouponUseCase:
    """Redeem one currently valid coupon atomically (INV-BILL-02)."""

    def __init__(self, repository, unit_of_work, outbox, clock) -> None:
        self._repository: IBillingGrowthRepository = repository
        self._unit_of_work: IBillingUnitOfWork = unit_of_work
        self._outbox: IBillingOutbox = outbox
        self._clock = clock

    def execute(self, merchant_id: UUID, code: str) -> ApplyCouponResult:
        """Lock coupon usage and append CouponRedeemed in the same transaction."""
        now = self._clock.now()
        with self._unit_of_work:
            self._repository.lock_merchant(merchant_id)
            coupon = self._repository.lock_coupon(code.strip().upper())
            if coupon is None:
                raise CouponNotFoundException("Coupon was not found.")
            if self._repository.merchant_has_redeemed_coupon(merchant_id, coupon.code):
                raise CouponAlreadyUsedException("Merchant already redeemed this coupon.")
            if (
                not coupon.is_active
                or coupon.valid_from > now
                or (coupon.valid_until is not None and coupon.valid_until < now)
                or (coupon.max_redemptions is not None and coupon.redemption_count >= coupon.max_redemptions)
                or coupon.discount_percent < 1
                or coupon.discount_percent > 100
                or coupon.duration_days < 1
            ):
                raise CouponNotValidException("Coupon is not valid.")
            expires_at = now + timedelta(days=coupon.duration_days)
            self._repository.record_coupon_redemption(
                merchant_id, coupon.code, now, expires_at
            )
            self._outbox.add(
                CouponRedeemed.create(
                    merchant_id, coupon.code, coupon.discount_percent, expires_at, now
                )
            )
        return ApplyCouponResult(coupon.code, coupon.discount_percent, now, expires_at)
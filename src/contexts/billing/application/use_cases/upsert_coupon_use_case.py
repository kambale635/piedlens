import re
from datetime import datetime

from shared_kernel.application_exceptions import ValidationException

from ..ports.growth_admin_repository import IBillingGrowthAdminRepository


class InvalidCouponDefinitionException(ValidationException):
    error_code = "INVALID_COUPON_DEFINITION"


class UpsertCouponUseCase:
    """Create or update a coupon's discount, usage limit, and validity window."""

    def __init__(self, repository: IBillingGrowthAdminRepository):
        self._repository = repository

    def execute(
        self,
        code: str,
        discount_percent: int,
        duration_days: int,
        max_redemptions: int | None,
        valid_from: datetime,
        valid_until: datetime | None,
        is_active: bool = True,
    ) -> dict:
        normalized_code = code.strip().upper()
        if (
            not re.fullmatch(r"[A-Z0-9_-]{2,64}", normalized_code)
            or not isinstance(discount_percent, int)
            or isinstance(discount_percent, bool)
            or not 1 <= discount_percent <= 100
            or not isinstance(duration_days, int)
            or isinstance(duration_days, bool)
            or duration_days < 1
            or (max_redemptions is not None and (
                not isinstance(max_redemptions, int)
                or isinstance(max_redemptions, bool)
                or max_redemptions < 1
            ))
            or not isinstance(valid_from, datetime)
            or valid_from.tzinfo is None
            or valid_from.utcoffset() is None
            or (valid_until is not None and valid_until <= valid_from)
            or (valid_until is not None and (
                valid_until.tzinfo is None or valid_until.utcoffset() is None
            ))
            or not isinstance(is_active, bool)
        ):
            raise InvalidCouponDefinitionException()
        return self._repository.upsert_coupon(
            normalized_code,
            discount_percent,
            duration_days,
            max_redemptions,
            valid_from,
            valid_until,
            is_active,
        )
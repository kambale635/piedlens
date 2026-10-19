from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..value_objects.identity_values import (
    CountryCode,
    CurrencyCode,
    LanguageCode,
)
from shared_kernel.domain_exceptions import DomainException


class DowngradeExceedsCurrentUsage(DomainException):
    """Raised when the requested plan limit is below current usage (INV-ID-03)."""

    status_code = 422
    error_code = "DOWNGRADE_EXCEEDS_CURRENT_USAGE"


@dataclass(frozen=True)
class Merchant:
    id: UUID
    name: str
    country: CountryCode
    preferred_language: LanguageCode
    currency: CurrencyCode
    subscription_plan: str
    created_at: datetime

    @classmethod
    def register(
        cls,
        merchant_id: UUID,
        name: str,
        country: CountryCode,
        preferred_language: LanguageCode,
        currency: CurrencyCode,
        created_at: datetime,
    ) -> "Merchant":
        """Create an independent Merchant aggregate on the Discovery plan."""
        normalized_name = name.strip()
        if not normalized_name:
            raise InvalidValueObjectException("Merchant name must not be empty.")
        return cls(
            merchant_id,
            normalized_name,
            country,
            preferred_language,
            currency,
            "discovery",
            created_at,
        )

    def change_plan(
        self, plan_code: str, active_connection_count: int, connection_limit: int | None
    ) -> "Merchant":
        """Change plan only when its connection limit covers usage (INV-ID-03)."""
        if connection_limit is not None and active_connection_count > connection_limit:
            raise DowngradeExceedsCurrentUsage()
        return Merchant(
            self.id,
            self.name,
            self.country,
            self.preferred_language,
            self.currency,
            plan_code,
            self.created_at,
        )
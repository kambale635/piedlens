from datetime import datetime

from shared_kernel.application_exceptions import ValidationException


class InvalidOutboundRateException(ValidationException):
    error_code = "INVALID_OUTBOUND_RATE"


class UpsertOutboundRateUseCase:
    """Create or update a country/category rate window without charging via Billing."""

    CATEGORIES = frozenset({"service", "utility", "marketing", "authentication"})

    def __init__(self, repository):
        self._repository = repository

    def execute(
        self,
        country: str,
        category: str,
        currency: str,
        amount_minor: int,
        valid_from: datetime,
        valid_until: datetime | None,
        is_active: bool = True,
    ) -> dict:
        if (
            not country
            or len(country) != 2
            or not country.isalpha()
            or category not in self.CATEGORIES
            or len(currency) != 3
            or not currency.isalpha()
            or not isinstance(amount_minor, int)
            or isinstance(amount_minor, bool)
            or amount_minor < 0
            or not isinstance(valid_from, datetime)
            or valid_from.tzinfo is None
            or (valid_until is not None and valid_until <= valid_from)
            or not isinstance(is_active, bool)
        ):
            raise InvalidOutboundRateException()
        return self._repository.upsert_outbound_rate(
            country.upper(), category, currency.upper(), amount_minor,
            valid_from, valid_until, is_active,
        )
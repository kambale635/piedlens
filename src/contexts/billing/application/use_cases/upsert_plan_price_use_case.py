from dataclasses import dataclass

from shared_kernel.application_exceptions import ResourceNotFoundException, ValidationException
from ..ports.plan_admin_repository import IPlanAdminRepository


class PlanNotFoundException(ResourceNotFoundException):
    error_code = "PLAN_NOT_FOUND"


class InvalidPlanPriceException(ValidationException):
    error_code = "INVALID_PLAN_PRICE"


@dataclass(frozen=True)
class UpsertPlanPriceResult:
    plan_code: str
    country: str
    currency: str
    period_days: int
    amount_minor: int
    is_active: bool


class UpsertPlanPriceUseCase:
    """Create or update one explicit country/currency plan price."""

    def __init__(self, repository: IPlanAdminRepository) -> None:
        self._repository = repository

    def execute(
        self,
        plan_code: str,
        country: str,
        currency: str,
        period_days: int,
        amount_minor: int,
        is_active: bool,
    ) -> UpsertPlanPriceResult:
        if (
            not country
            or (country != "*" and (len(country) != 2 or not country.isalpha()))
            or len(currency) != 3
            or not currency.isalpha()
            or period_days < 1
            or amount_minor < 0
        ):
            raise InvalidPlanPriceException()
        price = self._repository.upsert_price(
            plan_code=plan_code,
            country=country.upper() if country != "*" else country,
            currency=currency.upper(),
            period_days=period_days,
            amount_minor=amount_minor,
            is_active=is_active,
        )
        if price is None:
            raise PlanNotFoundException()
        return UpsertPlanPriceResult(
            price.plan_code,
            price.country,
            price.currency,
            price.period_days,
            price.amount_minor,
            price.is_active,
        )
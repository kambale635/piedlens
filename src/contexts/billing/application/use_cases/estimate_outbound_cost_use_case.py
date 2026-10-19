from dataclasses import dataclass

from shared_kernel.application_exceptions import ValidationException
from shared_kernel.ports import (
    IOutboundCostEstimator,
    IMerchantCountryReader,
    IMerchantCurrencyReader,
)


class OutboundRateNotConfiguredException(ValidationException):
    error_code = "OUTBOUND_RATE_NOT_CONFIGURED"


@dataclass(frozen=True)
class EstimateOutboundCostResult:
    country: str
    category: str
    count: int
    estimate: dict[str, object] | None


class EstimateOutboundCostUseCase:
    """Estimate configured platform fees; Meta bills the seller directly, never Billing."""

    CATEGORIES = frozenset({"service", "utility", "marketing", "authentication"})

    def __init__(
        self,
        merchant_countries: IMerchantCountryReader,
        merchant_currencies: IMerchantCurrencyReader,
        estimator: IOutboundCostEstimator,
    ):
        self._merchant_countries = merchant_countries
        self._merchant_currencies = merchant_currencies
        self._estimator = estimator

    def execute(self, merchant_id, category: str, count: int = 1) -> EstimateOutboundCostResult:
        if category not in self.CATEGORIES or not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValidationException("Outbound estimate request is invalid.")
        country = self._merchant_countries.country_code_for(merchant_id)
        if country is None:
            raise ValidationException("Merchant country is not configured.")
        currency = self._merchant_currencies.currency_for(merchant_id)
        estimate = self._estimator.estimate(country, currency, category, count)
        if estimate is None:
            raise OutboundRateNotConfiguredException("No outbound rate is configured.")
        return EstimateOutboundCostResult(country, category, count, estimate)
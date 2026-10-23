from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from shared_kernel.application_exceptions import ValidationException
from shared_kernel.ports import IMerchantCountryReader, IMerchantCurrencyReader
from shared_kernel.ports.outbound_cost_estimator import IOutboundCostEstimator


@dataclass(frozen=True)
class GenerateValueReportResult:
    """Return an outbound value summary with explicit pricing completeness metadata."""

    merchant_id: str
    country: str
    currency: str
    month: str
    total_amount_minor: int
    unpriced_message_count: int
    estimate_incomplete: bool
    items: list[dict]


class GenerateValueReportUseCase:
    """Aggregate the merchant's current-month outbound usage into a value report."""

    def __init__(
        self,
        merchant_country_reader: IMerchantCountryReader,
        merchant_currency_reader: IMerchantCurrencyReader,
        usage_reader,
        estimator: IOutboundCostEstimator,
    ):
        self._merchant_country_reader = merchant_country_reader
        self._merchant_currency_reader = merchant_currency_reader
        self._usage_reader = usage_reader
        self._estimator = estimator

    def execute(self, merchant_id) -> GenerateValueReportResult:
        """Build a monthly value report from the configured merchant country and active rates."""
        country = self._merchant_country_reader.country_code_for(merchant_id)
        if country is None:
            raise ValidationException("Merchant country is not configured.")

        currency = self._merchant_currency_reader.currency_for(merchant_id)
        current_month = date(timezone.now().year, timezone.now().month, 1)
        usage_rows = self._usage_reader.usage_for(merchant_id)

        items = []
        total_amount_minor = 0
        unpriced_message_count = 0

        for row in usage_rows:
            month_value = row.get("month")
            if month_value != current_month:
                continue
            category = row.get("category")
            count = int(row.get("count", 0))
            estimate = self._estimator.estimate(country, currency, category, count)
            if estimate is not None:
                amount_minor = int(estimate.get("amountMinor", 0) or 0)
                unit_amount_minor = int(estimate.get("unitAmountMinor", 0) or 0)
                total_amount_minor += amount_minor
                items.append(
                    {
                        "category": category,
                        "messages": count,
                        "unitAmountMinor": unit_amount_minor,
                        "amountMinor": amount_minor,
                        "currency": currency,
                    }
                )
            else:
                unpriced_message_count += count
                items.append(
                    {
                        "category": category,
                        "messages": count,
                        "priced": False,
                        "currency": currency,
                    }
                )

        items.sort(key=lambda item: item["category"])
        return GenerateValueReportResult(
            merchant_id=str(merchant_id),
            country=country,
            currency=currency,
            month=current_month.isoformat(),
            total_amount_minor=total_amount_minor,
            unpriced_message_count=unpriced_message_count,
            estimate_incomplete=unpriced_message_count > 0,
            items=items,
        )

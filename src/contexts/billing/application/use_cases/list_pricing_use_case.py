from dataclasses import dataclass

from shared_kernel.application_exceptions import ValidationException

from ..ports.pricing_reader import IPlanPricingReader


@dataclass(frozen=True)
class ListPricingResult:
    country: str
    plans: list[dict[str, object]]


class ListPricingUseCase:
    """List active plan prices for a country without currency conversion."""

    def __init__(self, pricing_reader: IPlanPricingReader) -> None:
        self._pricing_reader = pricing_reader

    def execute(self, country: str) -> ListPricingResult:
        normalized_country = country.strip().upper()
        if len(normalized_country) != 2 or not normalized_country.isalpha():
            raise ValidationException("Country must be a two-letter ISO country code.")
        return ListPricingResult(
            country=normalized_country,
            plans=self._pricing_reader.pricing_for_country(normalized_country),
        )

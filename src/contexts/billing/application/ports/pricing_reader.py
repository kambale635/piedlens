from typing import Protocol


class IPlanPricingReader(Protocol):
    """Read active plans and their explicitly configured country prices."""

    def pricing_for_country(self, country: str) -> list[dict[str, object]]:
        """Return each active plan with exact-country prices preferred over fallback prices."""

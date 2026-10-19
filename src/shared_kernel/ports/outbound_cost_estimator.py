from typing import Protocol


class IOutboundCostEstimator(Protocol):
    """Estimate configured third-party message fees without charging the merchant."""

    def estimate(
        self, country: str, currency: str, category: str, count: int
    ) -> dict[str, object] | None: ...
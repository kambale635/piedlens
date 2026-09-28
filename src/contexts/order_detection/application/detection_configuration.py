from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class DetectionConfiguration:
    """Merchant-resolved thresholds and correlation window supplied by configuration."""

    confidence_threshold: int
    correlation_window_days: int


class IDetectionConfiguration(Protocol):
    """Application port for resolving configurable detection rules."""

    def for_merchant(self, merchant_id: UUID) -> DetectionConfiguration:
        """Return the merchant's effective detection configuration."""
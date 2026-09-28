from dataclasses import dataclass

from shared_kernel.domain_exceptions import InvalidValueObjectException


@dataclass(frozen=True)
class ConfidenceScore:
    """Confidence value bounded to the inclusive interval [0, 100] (INV-RE-02)."""

    value: int

    def __post_init__(self) -> None:
        """Reject scores outside the domain range instead of silently clamping them."""
        if isinstance(self.value, bool) or not isinstance(self.value, int) or not 0 <= self.value <= 100:
            raise InvalidValueObjectException("Confidence score must be between 0 and 100.")
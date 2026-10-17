from dataclasses import dataclass

from shared_kernel.domain_exceptions import InvalidValueObjectException


@dataclass(frozen=True)
class LoyaltyScore:
    """CRM loyalty score bounded to [0, 100]."""

    value: int

    def __post_init__(self) -> None:
        """Reject invalid scores at construction."""
        if isinstance(self.value, bool) or not isinstance(self.value, int) or not 0 <= self.value <= 100:
            raise InvalidValueObjectException("Loyalty score must be between 0 and 100.")
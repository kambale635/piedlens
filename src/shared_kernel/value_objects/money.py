from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from shared_kernel.domain_exceptions import (
    CurrencyMismatchException,
    InvalidValueObjectException,
)


@dataclass(frozen=True, init=False)
class Money:
    """Represents a non-negative monetary amount paired with its ISO currency code.

    Money is shared across bounded contexts and prevents bare-number arithmetic
    (INV-TR-05, docs/16-business-invariants-and-rules.md).
    """

    amount: Decimal
    currency: str

    def __init__(self, amount: Decimal | int | str, currency: str) -> None:
        """Create an immutable amount and reject negative or malformed values."""
        try:
            normalized_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError) as error:
            raise InvalidValueObjectException("Money amount must be numeric.") from error

        normalized_currency = currency.upper()
        if not normalized_amount.is_finite() or normalized_amount < 0:
            raise InvalidValueObjectException("Money amount must be finite and non-negative.")
        if (
            len(normalized_currency) != 3
            or not normalized_currency.isascii()
            or not normalized_currency.isalpha()
        ):
            raise InvalidValueObjectException("Currency must be a three-letter ISO code.")

        object.__setattr__(self, "amount", normalized_amount)
        object.__setattr__(self, "currency", normalized_currency)

    def add(self, other: "Money") -> "Money":
        """Add same-currency amounts; protect INV-OD-05 and INV-TR-05."""
        if self.currency != other.currency:
            raise CurrencyMismatchException(
                f"Cannot add {self.currency} to {other.currency}."
            )
        return Money(self.amount + other.amount, self.currency)
from dataclasses import dataclass
from decimal import Decimal

from shared_kernel.domain_exceptions import InvalidValueObjectException
from shared_kernel.value_objects.money import Money


_SUPPORTED_FIELDS = {
    "total_spent": "total_spent",
    "totalspent": "total_spent",
    "order_count": "order_count",
    "ordercount": "order_count",
    "loyalty_score": "loyalty_score",
    "loyaltyscore": "loyalty_score",
    "tags": "tags",
}


@dataclass(frozen=True)
class SegmentRule:
    """Declarative rule used to calculate CRM segment membership dynamically."""

    field: str
    operator: str
    value: object

    def __post_init__(self) -> None:
        """Normalize and validate the segment rule contract before persistence."""
        normalized_field = _normalize_field(self.field)
        if normalized_field is None:
            raise InvalidValueObjectException("Unknown segment field.")
        if normalized_field == "tags":
            if self.operator != "contains" or not isinstance(self.value, str) or not self.value:
                raise InvalidValueObjectException("Tags support a non-empty contains value only.")
        elif self.operator not in {">", "<", "="}:
            raise InvalidValueObjectException("Numeric segment fields support >, <, and = only.")
        elif normalized_field == "total_spent":
            if not isinstance(self.value, Money):
                raise InvalidValueObjectException("Total spent segment thresholds must be Money.")
        elif (
            not isinstance(self.value, (int, Decimal))
            or isinstance(self.value, bool)
            or self.value < 0
        ):
            raise InvalidValueObjectException("Numeric segment thresholds must be non-negative numbers.")

        object.__setattr__(self, "field", normalized_field)


def _normalize_field(field: str) -> str | None:
    """Accept both snake_case and camelCase field names while enforcing CRM rules."""
    if not isinstance(field, str):
        return None
    normalized = field.strip()
    return _SUPPORTED_FIELDS.get(normalized.lower().replace("-", "_"))

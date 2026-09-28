from dataclasses import dataclass

from shared_kernel.domain_exceptions import InvalidValueObjectException


_SUPPORTED_FIELDS = {
    "total_spent": "total_spent",
    "totalspent": "total_spent",
    "order_count": "order_count",
    "ordercount": "order_count",
    "loyalty_score": "loyalty_score",
    "loyaltyscore": "loyalty_score",
}

_SUPPORTED_OPERATORS = {">", "<", "=", "contains"}


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
        if self.operator not in _SUPPORTED_OPERATORS:
            raise InvalidValueObjectException("Unsupported segment operator.")

        object.__setattr__(self, "field", normalized_field)


def _normalize_field(field: str) -> str | None:
    """Accept both snake_case and camelCase field names while enforcing CRM rules."""
    if not isinstance(field, str):
        return None
    normalized = field.strip()
    return _SUPPORTED_FIELDS.get(normalized.lower().replace("-", "_"))

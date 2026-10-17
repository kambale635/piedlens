from dataclasses import dataclass
from uuid import UUID

from ..exceptions.rule_scope_exceptions import InvalidRuleScopeException

@dataclass(frozen=True)
class RuleScope:
    """Normalized global, country, or merchant configuration scope (INV-RE-01)."""

    value: str

    @classmethod
    def parse(cls, value: str, merchant_id: UUID | None = None) -> "RuleScope":
        """Resolve a merchant alias from the trusted tenant ID and validate scope syntax."""
        if value == "global":
            return cls("global")
        if value == "merchant":
            if merchant_id is None:
                raise InvalidRuleScopeException("Merchant scope requires a tenant ID.")
            return cls(f"merchant:{merchant_id}")
        if value.startswith("merchant:"):
            try:
                requested_id = UUID(value.split(":", 1)[1])
            except ValueError as error:
                raise InvalidRuleScopeException("Merchant scope is malformed.") from error
            if merchant_id is None or requested_id != merchant_id:
                raise InvalidRuleScopeException("Rule scope is outside the current tenant.")
            return cls(f"merchant:{merchant_id}")
        if value.startswith("country:"):
            country = value.split(":", 1)[1]
            if len(country) == 2 and country.isalpha():
                return cls(f"country:{country.upper()}")
        raise InvalidRuleScopeException("Rule scope must be global, country:<code>, or merchant.")
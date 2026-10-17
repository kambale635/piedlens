from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from ...domain.value_objects.rule_type import RuleType

@dataclass(frozen=True)
class Rule:
    """A configured evaluator instruction whose language and pattern come from data (INV-RE-04)."""

    rule_id: UUID
    rule_type: RuleType
    language: str
    pattern: Any
    weight: int
    is_active: bool = True
    currency: str | None = None
    config: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        rule_type,
        language,
        pattern,
        weight,
        is_active=True,
        currency=None,
        config=None,
        rule_id=None,
    ):
        """Create an identified rule after its application contract has been validated."""
        return cls(
            rule_id=rule_id or uuid4(),
            rule_type=RuleType(rule_type),
            language=language,
            pattern=pattern,
            weight=weight,
            is_active=is_active,
            currency=currency,
            config=config or {},
        )
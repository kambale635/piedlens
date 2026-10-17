from dataclasses import dataclass
from uuid import UUID, uuid4

from .rule import Rule
from ..value_objects.rule_scope import RuleScope

@dataclass(frozen=True)
class RuleSet:
    """Configuration aggregate for one global, country, or merchant scope (INV-RE-01)."""

    id: UUID
    scope: RuleScope
    rules: tuple[Rule, ...]
    version: int

    @classmethod
    def create(cls, scope: RuleScope, rules: tuple[Rule, ...], version: int = 1):
        """Create a versioned RuleSet with an independent aggregate identity."""
        return cls(uuid4(), scope, rules, version)

    def adjust_weight(self, rule_id: UUID, was_correct: bool) -> "RuleSet":
        """Adjust one merchant rule by at most ten points per correction (INV-RE-03)."""
        adjustment = 10 if was_correct else -10
        updated_rules = tuple(
            Rule(
                rule_id=rule.rule_id,
                rule_type=rule.rule_type,
                language=rule.language,
                pattern=rule.pattern,
                weight=max(0, min(100, rule.weight + adjustment)),
                is_active=rule.is_active,
                currency=rule.currency,
                config=rule.config,
            )
            if rule.rule_id == rule_id
            else rule
            for rule in self.rules
        )
        return RuleSet(self.id, self.scope, updated_rules, self.version + 1)
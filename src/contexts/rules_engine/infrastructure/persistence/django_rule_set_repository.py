from uuid import UUID

from ...domain.entities.rule import Rule
from ...domain.entities.rule_set import RuleSet
from ...domain.value_objects.rule_scope import RuleScope
from ...domain.value_objects.rule_type import RuleType
from .models import RuleSetRecord


class DjangoRuleSetRepository:
    """Persist RuleSet configuration as JSON without language-specific code defaults."""

    def find_by_scope(self, scope: str) -> RuleSet | None:
        """Load a configuration aggregate by normalized scope key."""
        record = RuleSetRecord.objects.filter(scope=scope).first()
        if record is None:
            return None
        rules = tuple(
            Rule(
                rule_id=UUID(rule_data["rule_id"]),
                rule_type=RuleType(rule_data["rule_type"]),
                language=rule_data["language"],
                pattern=rule_data["pattern"],
                weight=rule_data["weight"],
                is_active=rule_data["is_active"],
                currency=rule_data.get("currency"),
                config=rule_data.get("config", {}),
            )
            for rule_data in record.rules
        )
        return RuleSet(record.id, RuleScope(record.scope), rules, record.version)

    def save(self, rule_set: RuleSet) -> None:
        """Persist configured patterns and versions as structured JSON data."""
        RuleSetRecord.objects.update_or_create(
            scope=rule_set.scope.value,
            defaults={
                "id": rule_set.id,
                "version": rule_set.version,
                "rules": [
                    {
                        "rule_id": str(rule.rule_id),
                        "rule_type": rule.rule_type.value,
                        "language": rule.language,
                        "pattern": rule.pattern,
                        "weight": rule.weight,
                        "is_active": rule.is_active,
                        "currency": rule.currency,
                        "config": rule.config,
                    }
                    for rule in rule_set.rules
                ],
            },
        )
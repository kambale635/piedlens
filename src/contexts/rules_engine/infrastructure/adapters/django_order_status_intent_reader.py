"""Module: contexts.rules_engine.infrastructure.adapters.django_order_status_intent_reader
Context: Rules Engine.
Role: expose configured message intent labels through a Rules Engine-owned adapter.
"""

from uuid import UUID

from contexts.identity.infrastructure.adapters.django_merchant_country_reader import (
    DjangoMerchantCountryReader,
)
from contexts.rules_engine.infrastructure.persistence.django_rule_set_repository import (
    DjangoRuleSetRepository,
)


class DjangoOrderStatusIntentReader:
    """Read active intent labels using merchant > country > global RuleSet precedence."""

    def __init__(self, rule_sets=None, country_reader=None) -> None:
        self._rule_sets = rule_sets or DjangoRuleSetRepository()
        self._country_reader = country_reader or DjangoMerchantCountryReader()

    def configured_intents(self, merchant_id: UUID) -> frozenset[str]:
        """Return configured intent labels available to message evaluation."""
        scopes = ["global"]
        country = self._country_reader.country_code_for(merchant_id)
        if country:
            scopes.append(f"country:{country}")
        scopes.append(f"merchant:{merchant_id}")

        selected_by_type = {}
        for scope in scopes:
            rule_set = self._rule_sets.find_by_scope(scope)
            if rule_set is None:
                continue
            by_type = {}
            for rule in rule_set.rules:
                by_type.setdefault(rule.rule_type, []).append(rule)
            selected_by_type.update(by_type)

        return frozenset(
            rule.config["intent"]
            for rules in selected_by_type.values()
            for rule in rules
            if rule.is_active
            and rule.rule_type.value == "ConfiguredIntent"
            and isinstance(rule.config.get("intent"), str)
        )

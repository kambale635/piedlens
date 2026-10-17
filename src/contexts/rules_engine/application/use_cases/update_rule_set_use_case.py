import re
from uuid import UUID

from ...domain.entities.rule import Rule
from ...domain.entities.rule_set import RuleSet
from ...domain.value_objects.rule_scope import RuleScope
from ...domain.value_objects.rule_type import RuleType
from ..exceptions import EmptyRulePatternException, InvalidRuleWeightException
from ..ports.rules_engine_ports import IRuleSetRepository, IRulesEngineUnitOfWork
from shared_kernel.application_exceptions import ValidationException


class UpdateRuleSetUseCase:
    """Validate and version one configured global, country, or merchant RuleSet.

    Contract: docs/15-use-cases-catalog.md#contexte-rules-engine.
    Scope precedence is enforced by evaluation (INV-RE-01); all language, currency,
    matching pattern, and formatting data are supplied by persisted rules (INV-RE-04).
    """

    def __init__(self, rule_sets: IRuleSetRepository, unit_of_work: IRulesEngineUnitOfWork):
        """Receive the Rules Engine repository and transaction ports."""
        self._rule_sets = rule_sets
        self._unit_of_work = unit_of_work

    def execute(
        self, scope: str, rules: list[dict], merchant_id: UUID | None = None
    ) -> dict:
        """Persist a validated RuleSet version without accepting untrusted tenant scope."""
        parsed_scope = RuleScope.parse(scope, merchant_id)
        normalized_rules = tuple(self._rule_from_data(data) for data in rules)
        existing = self._rule_sets.find_by_scope(parsed_scope.value)
        rule_set = RuleSet(
            id=existing.id if existing else RuleSet.create(parsed_scope, normalized_rules).id,
            scope=parsed_scope,
            rules=normalized_rules,
            version=existing.version + 1 if existing else 1,
        )
        with self._unit_of_work:
            self._rule_sets.save(rule_set)
        return {"rule_set_id": rule_set.id, "version": rule_set.version}

    @staticmethod
    def _rule_from_data(data: dict) -> Rule:
        """Validate rule shape and compile regex patterns before persistence."""
        if not isinstance(data, dict):
            raise ValidationException("Each rule must be an object.")
        weight = data.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, int) or not 0 <= weight <= 100:
            raise InvalidRuleWeightException("Rule weight must be between 0 and 100.")
        pattern = data.get("pattern")
        if pattern is None or pattern == "" or pattern == [] or pattern == {}:
            raise EmptyRulePatternException("Rule pattern must not be empty.")
        try:
            rule_type = RuleType(data.get("type"))
        except (TypeError, ValueError) as error:
            raise ValidationException("Unsupported rule type.") from error
        language = data.get("language")
        if not isinstance(language, str) or not language.strip():
            raise ValidationException("Rule language must be configured.")
        if rule_type is RuleType.AMOUNT_PATTERN:
            options = pattern if isinstance(pattern, dict) else {"regex": pattern}
            try:
                re.compile(options.get("regex", ""))
            except re.error as error:
                raise ValidationException("Amount rule regex is invalid.") from error
        return Rule.create(
            rule_type=rule_type,
            language=language,
            pattern=pattern,
            weight=weight,
            is_active=data.get("isActive", True) is True,
            currency=data.get("currency"),
            config=data.get("config", {}),
            rule_id=UUID(str(data["ruleId"])) if data.get("ruleId") else None,
        )
from uuid import UUID

from ..exceptions import RuleSetNotFoundException
from ..ports.rules_engine_ports import (
    IProcessedEventRepository,
    IRuleSetRepository,
    IRulesEngineUnitOfWork,
)


class AdjustRuleWeightFromCorrectionUseCase:
    """Adjust only one merchant RuleSet after feedback, bounded per correction (INV-RE-03).

    Contract: docs/15-use-cases-catalog.md#contexte-rules-engine.
    Global and country rules are never mutated by merchant feedback (INV-RE-01/03).
    """

    CONSUMER_NAME = "rules-engine-detection-correction"

    def __init__(self, rule_sets: IRuleSetRepository, processed_events: IProcessedEventRepository,
                 unit_of_work: IRulesEngineUnitOfWork) -> None:
        """Receive the RuleSet repository, idempotency ledger, and transaction boundary."""
        self._rule_sets = rule_sets
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work

    def execute(
        self,
        merchant_id: UUID,
        rule_id: UUID,
        was_correct: bool,
        *,
        event_id: UUID,
    ) -> dict | None:
        """Apply at most one bounded adjustment, once per correction event (INV-RE-03)."""
        scope = f"merchant:{merchant_id}"
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return None
            current = self._rule_sets.find_by_scope(scope)
            if current is None or not any(rule.rule_id == rule_id for rule in current.rules):
                raise RuleSetNotFoundException("Merchant rule was not found.")
            updated = current.adjust_weight(rule_id, was_correct)
            self._rule_sets.save(updated)
            self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
        rule = next(rule for rule in updated.rules if rule.rule_id == rule_id)
        return {"new_weight": rule.weight}
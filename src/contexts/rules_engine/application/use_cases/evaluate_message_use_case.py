from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from shared_kernel.application_exceptions import ResourceNotFoundException
from shared_kernel.ports import IMerchantCountryReader
from shared_kernel.value_objects.confidence_score import ConfidenceScore

from ...domain.events.rules_engine_events import MessageEvaluated
from ...domain.services.rule_evaluators import MessageContent
from ...domain.value_objects.rule_type import RuleType
from ..ports.rules_engine_ports import (
    IProcessedEventRepository,
    IRuleSetRepository,
    IRulesEngineOutbox,
    IRulesEngineUnitOfWork,
)


@dataclass(frozen=True)
class EvaluationResult:
    """Confidence, matched configured rules, and any extracted Money/intent values."""

    confidence_score: ConfidenceScore
    matched_rule_ids: tuple[UUID, ...]
    extracted_data: dict


class EvaluateMessageUseCase:
    """Evaluate a normalized message using merchant > country > global configured rules.

    Contract: docs/15-use-cases-catalog.md#contexte-rules-engine.
    Rule type precedence is strict (INV-RE-01), scores remain bounded without silent clamping
    (INV-RE-02), and all language/currency/pattern inputs come from RuleConfig (INV-RE-04).
    The consumer marker, result event, and outbox row share one transaction (INV-TR-02/03).
    """

    CONSUMER_NAME = "rules-engine-message-received"

    def __init__(
        self,
        rule_sets: IRuleSetRepository,
        country_reader: IMerchantCountryReader,
        evaluators: dict,
        processed_events: IProcessedEventRepository,
        unit_of_work: IRulesEngineUnitOfWork,
        outbox: IRulesEngineOutbox,
    ) -> None:
        """Receive rule, locale, strategy, idempotency, transaction and Outbox ports."""
        self._rule_sets = rule_sets
        self._country_reader = country_reader
        self._evaluators = evaluators
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(
        self,
        merchant_id: UUID,
        message_id: UUID,
        text_content: str,
        has_media: bool,
        conversation_context: tuple[dict, ...] = (),
        *,
        event_id: UUID,
        platform_connection_id: UUID | None = None,
        external_sender_id: str | None = None,
        display_name: str = "",
        message_event_id: UUID | None = None,
        source_message_timestamp: datetime | None = None,
    ) -> EvaluationResult | None:
        """Evaluate and publish once; return None for an already processed event."""
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return None
            result = self._evaluate(merchant_id, text_content, has_media, conversation_context)
            self._outbox.add(
                MessageEvaluated(
                    merchant_id=merchant_id,
                    message_id=message_id,
                    confidence_score=result.confidence_score.value,
                    matched_rule_ids=result.matched_rule_ids,
                    extracted_data=result.extracted_data,
                    occurred_at=datetime.now(timezone.utc),
                    platform_connection_id=platform_connection_id,
                    external_sender_id=external_sender_id,
                    display_name=display_name,
                    message_event_id=message_event_id or event_id,
                    source_message_timestamp=source_message_timestamp,
                )
            )
            self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
        return result

    def _evaluate(self, merchant_id, text_content, has_media, conversation_context):
        country = self._country_reader.country_code_for(merchant_id)
        scope_names = ["global"]
        if country:
            scope_names.append(f"country:{country}")
        scope_names.append(f"merchant:{merchant_id}")

        selected_by_type = {}
        for scope_name in scope_names:
            rule_set = self._rule_sets.find_by_scope(scope_name)
            if rule_set is None:
                continue
            by_type = {}
            for rule in rule_set.rules:
                by_type.setdefault(rule.rule_type, []).append(rule)
            selected_by_type.update(by_type)

        active_rules = [
            rule
            for scoped_rules in selected_by_type.values()
            for rule in scoped_rules
            if rule.is_active
        ]
        confidence_rules = [
            rule for rule in active_rules if rule.rule_type != RuleType.CONFIGURED_INTENT
        ]
        denominator = sum(rule.weight for rule in confidence_rules)
        message = MessageContent(text_content, has_media, conversation_context)
        matched_ids = []
        extracted_data = {}
        numerator = 0
        for rule in active_rules:
            evaluator = self._evaluators.get(rule.rule_type)
            if evaluator is None:
                continue
            outcome = evaluator.evaluate(message, rule)
            if outcome.matched:
                if rule.rule_type != RuleType.CONFIGURED_INTENT:
                    numerator += rule.weight
                matched_ids.append(rule.rule_id)
                extracted_data.update(outcome.extracted_data)
        score = round(numerator * 100 / denominator) if denominator else 0
        return EvaluationResult(
            confidence_score=ConfidenceScore(score),
            matched_rule_ids=tuple(matched_ids),
            extracted_data=extracted_data,
        )
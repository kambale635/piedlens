import unittest
from uuid import uuid4

from contexts.rules_engine.application.exceptions import (
    EmptyRulePatternException,
    InvalidRuleWeightException,
)
from contexts.rules_engine.application.use_cases.adjust_rule_weight_from_correction_use_case import (
    AdjustRuleWeightFromCorrectionUseCase,
)
from contexts.rules_engine.application.use_cases.evaluate_message_use_case import (
    EvaluateMessageUseCase,
)
from contexts.rules_engine.application.use_cases.update_rule_set_use_case import (
    UpdateRuleSetUseCase,
)
from contexts.rules_engine.domain.entities.rule import Rule
from contexts.rules_engine.domain.entities.rule_set import RuleSet
from contexts.rules_engine.domain.services.rule_evaluators import (
    AmountPatternEvaluator,
    EmojiMatchEvaluator,
    KeywordMatchEvaluator,
    MediaPresenceEvaluator,
)
from contexts.rules_engine.domain.value_objects.rule_scope import RuleScope
from contexts.rules_engine.domain.value_objects.rule_type import RuleType
from shared_kernel.value_objects.money import Money


class InMemoryRuleSetRepository:
    def __init__(self, values=()):
        self.values = {item.scope.value: item for item in values}

    def find_by_scope(self, scope):
        return self.values.get(scope)

    def save(self, rule_set):
        self.values[rule_set.scope.value] = rule_set


class InMemoryProcessedEvents:
    def __init__(self):
        self.values = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.values

    def mark_processed(self, event_id, consumer_name):
        self.values.add((event_id, consumer_name))


class FakeUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class FakeOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class FakeCountryReader:
    def country_code_for(self, merchant_id):
        return "CI"


def _rule(rule_type, pattern, weight=100, currency=None, config=None):
    return Rule.create(
        rule_type=rule_type,
        language="configured-language",
        pattern=pattern,
        weight=weight,
        currency=currency,
        config=config,
    )


class RulesEngineUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.evaluators = {
            RuleType.KEYWORD_MATCH: KeywordMatchEvaluator(),
            RuleType.AMOUNT_PATTERN: AmountPatternEvaluator(),
            RuleType.PAYMENT_PROOF_SIGNAL: MediaPresenceEvaluator(),
            RuleType.EMOJI_SIGNAL: EmojiMatchEvaluator(),
        }

    def test_specific_merchant_rules_override_country_and_global_type(self):
        global_rule = _rule(RuleType.KEYWORD_MATCH, ["global-token"])
        country_rule = _rule(RuleType.KEYWORD_MATCH, ["country-token"])
        merchant_rule = _rule(RuleType.KEYWORD_MATCH, ["merchant-token"])
        repository = InMemoryRuleSetRepository(
            [
                RuleSet.create(RuleScope("global"), (global_rule,)),
                RuleSet.create(RuleScope("country:CI"), (country_rule,)),
                RuleSet.create(RuleScope(f"merchant:{self.merchant_id}"), (merchant_rule,)),
            ]
        )
        use_case = EvaluateMessageUseCase(
            repository,
            FakeCountryReader(),
            self.evaluators,
            InMemoryProcessedEvents(),
            FakeUnitOfWork(),
            FakeOutbox(),
        )

        matched = use_case.execute(
            self.merchant_id, uuid4(), "merchant-token", False, event_id=uuid4()
        )
        shadowed = use_case.execute(
            self.merchant_id, uuid4(), "global-token", False, event_id=uuid4()
        )

        self.assertEqual(matched.confidence_score.value, 100)
        self.assertEqual(matched.matched_rule_ids, (merchant_rule.rule_id,))
        self.assertEqual(shadowed.confidence_score.value, 0)

    def test_amount_and_currency_are_extracted_only_from_rule_configuration(self):
        rule = _rule(
            RuleType.AMOUNT_PATTERN,
            {
                "regex": r"(?P<amount>\d+)(?P<currency>USD)",
                "groupSeparator": "",
                "decimalSeparator": ".",
            },
        )
        result = AmountPatternEvaluator().evaluate(
            type("Message", (), {"text": "250USD"})(), rule
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.extracted_data["amount"], Money("250", "USD"))

    def test_event_evaluation_is_idempotent_and_confidence_is_bounded(self):
        rule = _rule(RuleType.KEYWORD_MATCH, ["configured-token"], 25)
        repository = InMemoryRuleSetRepository(
            [RuleSet.create(RuleScope("global"), (rule,))]
        )
        processed = InMemoryProcessedEvents()
        outbox = FakeOutbox()
        use_case = EvaluateMessageUseCase(
            repository,
            FakeCountryReader(),
            self.evaluators,
            processed,
            FakeUnitOfWork(),
            outbox,
        )
        event_id = uuid4()

        first = use_case.execute(
            self.merchant_id, uuid4(), "configured-token", False, event_id=event_id
        )
        duplicate = use_case.execute(
            self.merchant_id, uuid4(), "configured-token", False, event_id=event_id
        )

        self.assertEqual(first.confidence_score.value, 100)
        self.assertIsNone(duplicate)
        self.assertEqual(len(outbox.events), 1)

    def test_update_rejects_weight_and_empty_pattern(self):
        use_case = UpdateRuleSetUseCase(InMemoryRuleSetRepository(), FakeUnitOfWork())

        with self.assertRaises(InvalidRuleWeightException):
            use_case.execute("global", [{"type": "KeywordMatch", "language": "en", "pattern": ["x"], "weight": 101}])
        with self.assertRaises(EmptyRulePatternException):
            use_case.execute("global", [{"type": "KeywordMatch", "language": "en", "pattern": [], "weight": 10}])

    def test_correction_adjustment_is_bounded_to_ten_and_merchant_rule_set(self):
        rule = _rule(RuleType.KEYWORD_MATCH, ["configured"], 95)
        repository = InMemoryRuleSetRepository(
            [RuleSet.create(RuleScope(f"merchant:{self.merchant_id}"), (rule,))]
        )
        use_case = AdjustRuleWeightFromCorrectionUseCase(
            repository, InMemoryProcessedEvents(), FakeUnitOfWork()
        )

        event_id = uuid4()
        result = use_case.execute(self.merchant_id, rule.rule_id, True, event_id=event_id)
        duplicate = use_case.execute(self.merchant_id, rule.rule_id, True, event_id=event_id)

        self.assertEqual(result["new_weight"], 100)
        self.assertIsNone(duplicate)
        self.assertEqual(repository.find_by_scope(f"merchant:{self.merchant_id}").version, 2)


if __name__ == "__main__":
    unittest.main()
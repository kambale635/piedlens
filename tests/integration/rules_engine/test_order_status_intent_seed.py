from django.core.management import call_command
from django.test import TestCase
from uuid import uuid4

from contexts.rules_engine.domain.services.rule_evaluators import (
    KeywordMatchEvaluator,
    MessageContent,
)
from contexts.rules_engine.domain.value_objects.rule_type import RuleType
from contexts.rules_engine.infrastructure.persistence.django_rule_set_repository import (
    DjangoRuleSetRepository,
)
from contexts.rules_engine.infrastructure.adapters.django_order_status_intent_reader import (
    DjangoOrderStatusIntentReader,
)


class OrderStatusIntentSeedTests(TestCase):
    def test_seed_is_idempotent_and_configures_french_and_english_signals(self):
        call_command("seed_order_status_intents", verbosity=0)
        repository = DjangoRuleSetRepository()
        first = repository.find_by_scope("global")
        initial_count = len(first.rules)
        call_command("seed_order_status_intents", verbosity=0)
        second = repository.find_by_scope("global")

        self.assertEqual(len(second.rules), initial_count)
        class CountryReader:
            def country_code_for(self, merchant_id):
                return None

        configured = DjangoOrderStatusIntentReader(
            rule_sets=repository,
            country_reader=CountryReader(),
        ).configured_intents(uuid4())
        self.assertEqual(
            configured,
            frozenset({"payment_received", "delivery_confirmed"}),
        )
        rules = [
            rule for rule in second.rules if rule.rule_type == RuleType.CONFIGURED_INTENT
        ]
        evaluator = KeywordMatchEvaluator()
        samples = (
            ("c'est payé", "payment_received"),
            ("paid", "payment_received"),
            ("bien reçu", "delivery_confirmed"),
            ("delivered", "delivery_confirmed"),
        )
        for phrase, expected_intent in samples:
            with self.subTest(phrase=phrase):
                matches = [
                    evaluator.evaluate(MessageContent(phrase, False), rule)
                    for rule in rules
                ]
                intents = [result.extracted_data["intent"] for result in matches if result.matched]
                self.assertIn(expected_intent, intents)
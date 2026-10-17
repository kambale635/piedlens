import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from shared_kernel.value_objects.money import Money

from ..entities.rule import Rule

@dataclass(frozen=True)
class MessageContent:
    """Normalized text/media input to pure Rule evaluator strategies."""

    text: str
    has_media: bool
    conversation_context: tuple[dict, ...] = ()

@dataclass(frozen=True)
class RuleEvaluation:
    """Boolean strategy match and optional configuration-derived extracted data."""

    matched: bool
    extracted_data: dict

class KeywordMatchEvaluator:
    """Match configured keywords without embedding any language-specific vocabulary."""

    def evaluate(self, message: MessageContent, rule: Rule) -> RuleEvaluation:
        """Return the matched configured keyword and optional configured intent label."""
        values = rule.pattern if isinstance(rule.pattern, list) else [rule.pattern]
        text = message.text.casefold()
        matched_value = next(
            (value for value in values if isinstance(value, str) and value.casefold() in text),
            None,
        )
        extracted = {}
        if matched_value is not None and rule.config.get("intent"):
            extracted["intent"] = rule.config["intent"]
        return RuleEvaluation(matched_value is not None, extracted)

class AmountPatternEvaluator:
    """Extract configured amount/currency patterns without a locale or currency fallback."""

    def evaluate(self, message: MessageContent, rule: Rule) -> RuleEvaluation:
        """Parse the named amount group with separators supplied by RuleConfig."""
        options = rule.pattern if isinstance(rule.pattern, dict) else {"regex": rule.pattern}
        expression = options.get("regex")
        if not isinstance(expression, str) or not expression:
            return RuleEvaluation(False, {})
        match = re.search(expression, message.text, re.IGNORECASE)
        if match is None:
            return RuleEvaluation(False, {})
        amount_text = match.groupdict().get("amount") or (match.group(1) if match.groups() else "")
        currency = rule.currency or options.get("currency") or match.groupdict().get("currency")
        if not amount_text or not currency:
            return RuleEvaluation(False, {})
        if "groupSeparator" not in options or "decimalSeparator" not in options:
            return RuleEvaluation(False, {})
        group_separator = options["groupSeparator"]
        decimal_separator = options["decimalSeparator"]
        normalized = amount_text.replace(group_separator, "") if group_separator else amount_text
        if decimal_separator != ".":
            normalized = normalized.replace(decimal_separator, ".")
        try:
            amount = Money(Decimal(normalized), currency)
        except (InvalidOperation, ValueError, TypeError):
            return RuleEvaluation(False, {})
        return RuleEvaluation(True, {"amount": amount, "currency": amount.currency})

class MediaPresenceEvaluator:
    """Treat attached media as evidence only when a configured media rule is active."""

    def evaluate(self, message: MessageContent, rule: Rule) -> RuleEvaluation:
        """Return whether the normalized message contains media."""
        return RuleEvaluation(message.has_media, {})

class EmojiMatchEvaluator:
    """Match configured emoji tokens without hard-coded signals."""

    def evaluate(self, message: MessageContent, rule: Rule) -> RuleEvaluation:
        """Return whether any configured token occurs in the message text."""
        values = rule.pattern if isinstance(rule.pattern, list) else [rule.pattern]
        return RuleEvaluation(
            any(value in message.text for value in values if isinstance(value, str)), {}
        )
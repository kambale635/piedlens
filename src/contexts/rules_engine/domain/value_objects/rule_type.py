from enum import StrEnum

class RuleType(StrEnum):
    """Evaluator strategies configured by RuleSet data, not message-language code."""

    KEYWORD_MATCH = "KeywordMatch"
    AMOUNT_PATTERN = "AmountPattern"
    PAYMENT_PROOF_SIGNAL = "PaymentProofSignal"
    EMOJI_SIGNAL = "EmojiSignal"
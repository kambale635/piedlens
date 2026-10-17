# Rules Engine

Shared stateless message-evaluation context using configured rules, scope precedence, idempotent event consumption, and per-merchant correction feedback. No message-language keywords, currencies, or detection patterns are hard-coded.

Reference: [docs/08-context-rules-engine.md](../../../docs/08-context-rules-engine.md).

Use Cases: [EvaluateMessageUseCase](../../../docs/15-use-cases-catalog.md#contexte-rules-engine), `UpdateRuleSetUseCase`, `AdjustRuleWeightFromCorrectionUseCase`.

Tests: `python manage.py test tests.unit.rules_engine`.
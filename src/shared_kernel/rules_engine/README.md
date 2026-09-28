# Rules Engine

Shared configurable message-evaluation context used by the MVP business contexts.

Reference: [docs/08-context-rules-engine.md](../../../docs/08-context-rules-engine.md).

Use Cases: [EvaluateMessageUseCase](../../../docs/15-use-cases-catalog.md#contexte-rules-engine), UpdateRuleSetUseCase, AdjustRuleWeightFromCorrectionUseCase.

Tests: `docker compose run --rm django python manage.py test tests.unit.rules_engine`.
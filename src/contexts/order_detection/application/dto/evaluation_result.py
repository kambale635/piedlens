from dataclasses import dataclass
from uuid import UUID

from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


@dataclass(frozen=True)
class EvaluationResult:
    """Rules Engine result consumed by Order Detection without importing its internals."""

    confidence_score: ConfidenceScore
    intent: str | None
    amount: Money | None
    matched_rule_ids: tuple[UUID, ...] = ()
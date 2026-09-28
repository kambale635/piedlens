from typing import Any

from ..domain.segment import CRMSegment
from ..domain.segment_rule import SegmentRule
from .exceptions import (
    UnknownSegmentFieldException,
    UnsupportedSegmentOperatorException,
)


class CreateSegmentUseCase:
    """Create a merchant segment from a validated declarative rule."""

    _SUPPORTED_FIELDS = {
        "total_spent": "total_spent",
        "totalspent": "total_spent",
        "order_count": "order_count",
        "ordercount": "order_count",
        "loyalty_score": "loyalty_score",
        "loyaltyscore": "loyalty_score",
    }
    _SUPPORTED_OPERATORS = {">", "<", "=", "contains"}

    def __init__(self, segment_repository):
        """Receive the CRM segment persistence port through dependency injection."""
        self._segment_repository = segment_repository

    def execute(
        self,
        merchant_id,
        name: str,
        definition_rule: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a segment only when its field and operator are authorized by CRM rules."""
        field_name = definition_rule.get("field")
        field = self._normalize_field(field_name)
        if field is None:
            raise UnknownSegmentFieldException("Unknown segment field.")

        operator = definition_rule.get("operator")
        if operator not in self._SUPPORTED_OPERATORS:
            raise UnsupportedSegmentOperatorException("Unsupported segment operator.")

        rule = SegmentRule(field=field, operator=operator, value=definition_rule.get("value"))
        segment = CRMSegment.create(
            merchant_id=merchant_id,
            name=name,
            definition_rule=rule,
        )
        self._segment_repository.save(segment)
        return {"segment_id": segment.id}

    @classmethod
    def _normalize_field(cls, field_name: Any) -> str | None:
        """Normalize common field-name shapes while preserving the CRM contract."""
        if not isinstance(field_name, str):
            return None
        normalized = field_name.strip()
        return cls._SUPPORTED_FIELDS.get(normalized.lower().replace("-", "_"))

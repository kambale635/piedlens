from typing import Any
from uuid import UUID

from shared_kernel.domain_exceptions import InvalidValueObjectException
from shared_kernel.value_objects.money import Money

from ...domain.entities.segment import CRMSegment
from ...domain.value_objects.segment_rule import SegmentRule
from ..exceptions import (
    InvalidSegmentValueException,
    SegmentCurrencyRequiredException,
    UnknownSegmentFieldException,
    UnsupportedSegmentOperatorException,
)


class CreateSegmentUseCase:
    """Create a merchant segment from a validated declarative rule.

    Contract: docs/15-use-cases-catalog.md#contexte-crm.
    Monetary thresholds use a Money value and never compare across currencies.
    """

    _SUPPORTED_FIELDS = {
        "total_spent": "total_spent",
        "totalspent": "total_spent",
        "order_count": "order_count",
        "ordercount": "order_count",
        "loyalty_score": "loyalty_score",
        "loyaltyscore": "loyalty_score",
        "tags": "tags",
    }

    def __init__(self, segment_repository) -> None:
        """Receive the CRM segment persistence port through dependency injection."""
        self._segment_repository = segment_repository

    def execute(
        self,
        merchant_id: UUID,
        name: str,
        definition_rule: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a segment only when its field and operator are authorized by CRM rules."""
        if not isinstance(definition_rule, dict):
            raise InvalidSegmentValueException("Segment definition must be an object.")
        field_name = definition_rule.get("field")
        field = self._normalize_field(field_name)
        if field is None:
            raise UnknownSegmentFieldException("Unknown segment field.")

        operator = definition_rule.get("operator")
        if (field == "tags" and operator != "contains") or (
            field != "tags" and operator not in {">", "<", "="}
        ):
            raise UnsupportedSegmentOperatorException("Unsupported segment operator.")

        value = definition_rule.get("value")
        if field == "total_spent":
            if not isinstance(value, dict) or "currency" not in value:
                raise SegmentCurrencyRequiredException("Total spent rules require a currency.")
            if "amount" not in value:
                raise InvalidSegmentValueException(
                    "Total spent thresholds require an amount."
                )
            try:
                value = Money(value["amount"], value["currency"])
            except (InvalidValueObjectException, TypeError, ValueError) as error:
                raise InvalidSegmentValueException("Invalid Money threshold.") from error

        try:
            rule = SegmentRule(field=field, operator=operator, value=value)
        except InvalidValueObjectException as error:
            raise InvalidSegmentValueException("Invalid segment rule value.") from error
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

"""Module: contexts/crm/infrastructure/django_segment_repository.py
Context: CRM.
Role: persist merchant-scoped dynamic segment definitions.
"""

from decimal import Decimal
from uuid import UUID

from shared_kernel.value_objects.money import Money

from ...domain.entities.segment import CRMSegment
from ...domain.value_objects.segment_rule import SegmentRule
from ..persistence.models import SegmentRecord


class DjangoSegmentRepository:
    """Persist and rehydrate CRM segment aggregates without storing membership."""

    def save(self, segment: CRMSegment) -> None:
        """Persist the declarative rule; membership is always calculated dynamically."""
        rule_value = segment.definition_rule.value
        if isinstance(rule_value, Money):
            rule_value = {
                "amount": str(rule_value.amount),
                "currency": rule_value.currency,
            }
        SegmentRecord.objects.update_or_create(
            id=segment.id,
            defaults={
                "merchant_id": segment.merchant_id,
                "name": segment.name,
                "rule_field": segment.definition_rule.field,
                "rule_operator": segment.definition_rule.operator,
                "rule_value": rule_value,
            },
        )

    def find_by_id(self, segment_id: UUID) -> CRMSegment | None:
        """Load one segment definition for its dynamic membership query."""
        record = SegmentRecord.objects.filter(id=segment_id).first()
        return self._to_domain(record) if record else None

    def find_by_merchant(self, merchant_id: UUID) -> list[CRMSegment]:
        """List a merchant's segments in stable identifier order."""
        records = SegmentRecord.objects.filter(merchant_id=merchant_id).order_by("id")
        return [self._to_domain(record) for record in records]

    @staticmethod
    def _to_domain(record: SegmentRecord) -> CRMSegment:
        """Rehydrate the typed rule value from its JSON persistence representation."""
        value = record.rule_value
        if record.rule_field == "total_spent":
            value = Money(Decimal(value["amount"]), value["currency"])
        return CRMSegment(
            id=record.id,
            merchant_id=record.merchant_id,
            name=record.name,
            definition_rule=SegmentRule(
                field=record.rule_field,
                operator=record.rule_operator,
                value=value,
            ),
        )
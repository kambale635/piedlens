from __future__ import annotations

from typing import Any

from shared_kernel.value_objects.money import Money

from ..entities.contact import Contact
from ..value_objects.contact_status import ContactStatus
from ..value_objects.segment_rule import SegmentRule


class SegmentMembershipCalculator:
    """Evaluate whether a Contact belongs to a dynamic CRM segment.

    The calculator is a pure domain service: it evaluates the declarative rule
    without mutating the Contact aggregate or persisting state. This preserves the
    CRM aggregate boundary and the dynamic nature of CRMSegment membership. Monetary
    membership is evaluated in the rule's declared currency only (INV-CRM-08).
    """

    def evaluate(self, rule: SegmentRule, contacts: list[Contact]) -> list[Contact]:
        """Return the contacts whose values satisfy the CRM segment rule."""
        return [
            contact
            for contact in contacts
            if contact.status is ContactStatus.ACTIVE and self._matches(rule, contact)
        ]

    def _matches(self, rule: SegmentRule, contact: Contact) -> bool:
        """Compare the rule against a single Contact aggregate."""
        if rule.field == "tags":
            return rule.value in contact.tags
        if rule.field == "total_spent":
            value = self._extract_value(contact, rule.field, rule.value.currency)
            threshold = rule.value.amount
        else:
            value = self._extract_value(contact, rule.field)
            threshold = rule.value
        if rule.operator == ">":
            return value > threshold
        if rule.operator == "<":
            return value < threshold
        return value == threshold

    @staticmethod
    def _extract_value(
        contact: Contact,
        field: str,
        currency: str | None = None,
    ) -> Any:
        """Read the field value from the Contact aggregate using the declared rule key."""
        if field == "total_spent":
            # A contact with no recorded spend in this currency has a zero total.
            total = Money("0", currency)
            for money in contact.total_spent_by_currency:
                if money.currency == currency:
                    total = total.add(money)
            return total.amount
        if field == "order_count":
            return contact.order_count
        if field == "loyalty_score":
            return contact.loyalty_score.value
        return 0

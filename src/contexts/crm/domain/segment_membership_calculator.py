from __future__ import annotations

from typing import Any

from .contact import Contact
from .segment_rule import SegmentRule


class SegmentMembershipCalculator:
    """Evaluate whether a Contact belongs to a dynamic CRM segment.

    The calculator is a pure domain service: it evaluates the declarative rule
    without mutating the Contact aggregate or persisting state. This preserves the
    CRM aggregate boundary and the dynamic nature of CRMSegment membership.
    """

    def evaluate(self, rule: SegmentRule, contacts: list[Contact]) -> list[Contact]:
        """Return the contacts whose values satisfy the CRM segment rule."""
        return [contact for contact in contacts if self._matches(rule, contact)]

    def _matches(self, rule: SegmentRule, contact: Contact) -> bool:
        """Compare the rule against a single Contact aggregate."""
        value = self._extract_value(contact, rule.field)
        if rule.operator == ">":
            return value > rule.value
        if rule.operator == "<":
            return value < rule.value
        if rule.operator == "=":
            return value == rule.value
        if rule.operator == "contains":
            if isinstance(value, (str, list, tuple, set)):
                return str(rule.value) in str(value)
            return False
        return False

    @staticmethod
    def _extract_value(contact: Contact, field: str) -> Any:
        """Read the field value from the Contact aggregate using the declared rule key."""
        if field == "total_spent":
            return sum(
                (money.amount for money in contact.total_spent_by_currency),
                start=0,
            )
        if field == "order_count":
            return contact.order_count
        if field == "loyalty_score":
            return contact.loyalty_score.value
        return 0

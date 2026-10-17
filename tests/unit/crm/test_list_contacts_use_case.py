import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.exceptions import (
    InvalidSegmentPaginationException,
    SegmentNotFoundException,
)
from contexts.crm.application.use_cases.list_contacts_use_case import ListContactsUseCase
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.domain.entities.segment import CRMSegment
from contexts.crm.domain.value_objects.segment_rule import SegmentRule
from shared_kernel.value_objects.money import Money


class InMemoryContactRepository:
    def __init__(self, contacts):
        self.contacts = contacts

    def find_by_merchant(self, merchant_id):
        return [contact for contact in self.contacts if contact.merchant_id == merchant_id]


class InMemorySegmentRepository:
    def __init__(self, segments):
        self.segments = {segment.id: segment for segment in segments}

    def find_by_id(self, segment_id):
        return self.segments.get(segment_id)


class ListContactsUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.other_merchant_id = uuid4()
        self.contacts = [
            self._contact(self.merchant_id, "A", 3),
            self._contact(self.merchant_id, "B", 1),
            self._contact(self.other_merchant_id, "Other", 9),
        ]
        self.segment = CRMSegment.create(
            self.merchant_id,
            "Frequent",
            SegmentRule(field="order_count", operator=">", value=1),
        )
        self.use_case = ListContactsUseCase(
            InMemoryContactRepository(self.contacts),
            InMemorySegmentRepository([self.segment]),
        )

    def test_lists_only_merchant_contacts_with_pagination(self):
        result = self.use_case.execute(self.merchant_id, page=2, page_size=1)

        self.assertEqual(result["total_count"], 2)
        self.assertEqual(len(result["contacts"]), 1)
        self.assertEqual(result["contacts"][0]["display_name"], "B")

    def test_filters_membership_dynamically_and_checks_segment_scope(self):
        result = self.use_case.execute(self.merchant_id, self.segment.id)

        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["contacts"][0]["display_name"], "A")
        with self.assertRaises(SegmentNotFoundException):
            self.use_case.execute(self.other_merchant_id, self.segment.id)

    def test_rejects_invalid_page_size(self):
        with self.assertRaises(InvalidSegmentPaginationException):
            self.use_case.execute(self.merchant_id, page_size=101)

    def _contact(self, merchant_id, name, order_count):
        return Contact(
            id=uuid4(),
            merchant_id=merchant_id,
            platform_connection_id=uuid4(),
            external_identifier=name.lower(),
            display_name=name,
            total_spent_by_currency=(Money("0", "XOF"),),
            order_count=order_count,
            last_interaction_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            loyalty_score=type("LoyaltyScore", (), {"value": 0})(),
            tags=(),
        )


if __name__ == "__main__":
    unittest.main()
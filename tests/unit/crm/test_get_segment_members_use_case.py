import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.use_cases.get_segment_members_use_case import GetSegmentMembersUseCase
from contexts.crm.application.exceptions import (
    InvalidSegmentPaginationException,
    SegmentNotFoundException,
)
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.domain.value_objects.contact_status import ContactStatus
from contexts.crm.domain.entities.segment import CRMSegment
from contexts.crm.domain.value_objects.segment_rule import SegmentRule
from contexts.crm.domain.services.segment_membership_calculator import SegmentMembershipCalculator
from shared_kernel.value_objects.money import Money


class InMemoryContactRepository:
    def __init__(self):
        self.contacts_by_merchant = {}

    def find_by_merchant(self, merchant_id):
        return self.contacts_by_merchant.get(merchant_id, [])


class InMemorySegmentRepository:
    def __init__(self, segment=None):
        self.segment = segment

    def find_by_id(self, segment_id):
        if self.segment and self.segment.id == segment_id:
            return self.segment
        return None


class InMemoryMembershipCache:
    def __init__(self):
        self.values = {}
        self.get_calls = 0
        self.set_calls = 0

    def get_members(self, segment_id, merchant_id, page, page_size):
        self.get_calls += 1
        return self.values.get((segment_id, merchant_id, page, page_size))

    def set_members(self, segment_id, merchant_id, page, page_size, result):
        self.set_calls += 1
        self.values[(segment_id, merchant_id, page, page_size)] = result

    def invalidate_merchant(self, merchant_id):
        self.values = {
            key: value
            for key, value in self.values.items()
            if key[1] != merchant_id
        }


class GetSegmentMembersUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.contact_repository = InMemoryContactRepository()
        self.segment = CRMSegment.create(
            merchant_id=self.merchant_id,
            name="VIP clients",
            definition_rule=SegmentRule(field="order_count", operator=">", value=1),
        )
        self.segment_repository = InMemorySegmentRepository(self.segment)
        self.membership_cache = InMemoryMembershipCache()
        self.contact_repository.contacts_by_merchant[self.merchant_id] = [
            Contact(
                id=uuid4(),
                merchant_id=self.merchant_id,
                platform_connection_id=uuid4(),
                external_identifier="a",
                display_name="A",
                total_spent_by_currency=(Money("60000", "XOF"), Money("90000", "USD")),
                order_count=2,
                last_interaction_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
                loyalty_score=type("LoyaltyScore", (), {"value": 50})(),
                tags=(),
            ),
            Contact(
                id=uuid4(),
                merchant_id=self.merchant_id,
                platform_connection_id=uuid4(),
                external_identifier="b",
                display_name="B",
                total_spent_by_currency=(Money("0", "XOF"), Money("100000", "USD")),
                order_count=1,
                last_interaction_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
                loyalty_score=type("LoyaltyScore", (), {"value": 20})(),
                tags=(),
            ),
        ]
        self.use_case = GetSegmentMembersUseCase(
            contact_repository=self.contact_repository,
            segment_repository=self.segment_repository,
            membership_cache=self.membership_cache,
        )

    def test_returns_only_contacts_matching_segment_rule(self):
        result = self.use_case.execute(segment_id=self.segment.id, page=1, page_size=50)

        self.assertEqual(result["total_count"], 1)
        self.assertEqual(len(result["contacts"]), 1)
        self.assertEqual(result["contacts"][0]["contact_id"], self.contact_repository.contacts_by_merchant[self.merchant_id][0].id)

    def test_total_spent_compares_only_the_declared_currency(self):
        calculator = SegmentMembershipCalculator()
        contacts = self.contact_repository.contacts_by_merchant[self.merchant_id]
        rule = SegmentRule(
            field="total_spent",
            operator=">",
            value=Money("50000", "XOF"),
        )

        matching = calculator.evaluate(rule, contacts)

        self.assertEqual([contact.id for contact in matching], [contacts[0].id])

    def test_tag_contains_uses_exact_membership(self):
        calculator = SegmentMembershipCalculator()
        contacts = self.contact_repository.contacts_by_merchant[self.merchant_id]
        contacts[0].tags = ("vip",)
        contacts[1].tags = ("not-vip",)
        rule = SegmentRule(field="tags", operator="contains", value="vip")

        matching = calculator.evaluate(rule, contacts)

        self.assertEqual([contact.id for contact in matching], [contacts[0].id])

    def test_merged_tombstones_are_excluded_from_segments(self):
        contacts = self.contact_repository.contacts_by_merchant[self.merchant_id]
        contacts[0].status = ContactStatus.MERGED
        result = self.use_case.execute(segment_id=self.segment.id)

        self.assertEqual(result["total_count"], 0)

    def test_rejects_invalid_pagination_and_missing_segment(self):
        with self.assertRaises(InvalidSegmentPaginationException):
            self.use_case.execute(segment_id=self.segment.id, page=0)
        with self.assertRaises(SegmentNotFoundException):
            self.use_case.execute(segment_id=uuid4())

    def test_caches_page_and_returns_cached_result(self):
        first = self.use_case.execute(segment_id=self.segment.id, page=1, page_size=1)
        second = self.use_case.execute(segment_id=self.segment.id, page=1, page_size=1)

        self.assertEqual(first, second)
        self.assertEqual(self.membership_cache.set_calls, 1)
        self.assertEqual(self.membership_cache.get_calls, 2)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.get_segment_members_use_case import GetSegmentMembersUseCase
from contexts.crm.domain.contact import Contact
from contexts.crm.domain.segment import CRMSegment
from contexts.crm.domain.segment_rule import SegmentRule
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
        self.contact_repository.contacts_by_merchant[self.merchant_id] = [
            Contact(
                id=uuid4(),
                merchant_id=self.merchant_id,
                platform_connection_id=uuid4(),
                external_identifier="a",
                display_name="A",
                total_spent_by_currency=(Money("0", "XOF"),),
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
                total_spent_by_currency=(Money("0", "XOF"),),
                order_count=1,
                last_interaction_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
                loyalty_score=type("LoyaltyScore", (), {"value": 20})(),
                tags=(),
            ),
        ]
        self.use_case = GetSegmentMembersUseCase(
            contact_repository=self.contact_repository,
            segment_repository=self.segment_repository,
        )

    def test_returns_only_contacts_matching_segment_rule(self):
        result = self.use_case.execute(segment_id=self.segment.id, page=1, page_size=50)

        self.assertEqual(result["total_count"], 1)
        self.assertEqual(len(result["contacts"]), 1)
        self.assertEqual(result["contacts"][0]["contact_id"], self.contact_repository.contacts_by_merchant[self.merchant_id][0].id)


if __name__ == "__main__":
    unittest.main()

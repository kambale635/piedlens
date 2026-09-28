import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.send_bulk_message_use_case import SendBulkMessageUseCase
from contexts.crm.domain.contact import Contact
from contexts.crm.domain.segment import CRMSegment
from contexts.crm.domain.segment_rule import SegmentRule
from shared_kernel.value_objects.money import Money


class InMemorySegmentRepository:
    def __init__(self, segment):
        self.segment = segment

    def find_by_id(self, segment_id):
        if self.segment and self.segment.id == segment_id:
            return self.segment
        return None


class InMemoryContactRepository:
    def __init__(self, contacts):
        self.contacts = contacts

    def find_by_merchant(self, merchant_id):
        return [contact for contact in self.contacts if contact.merchant_id == merchant_id]


class InMemoryRateLimiter:
    def __init__(self):
        self.calls = []

    def check_allowed(self, channel):
        self.calls.append(channel)
        return True


class InMemoryMessageSender:
    def __init__(self):
        self.sent = []

    def send_message(self, channel, contact, template):
        self.sent.append((channel, contact.id, template))
        return {"status": "queued"}


class SendBulkMessageUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.segment = CRMSegment.create(
            merchant_id=self.merchant_id,
            name="VIP",
            definition_rule=SegmentRule(field="order_count", operator=">", value=1),
        )
        self.contacts = [
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
                order_count=3,
                last_interaction_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
                loyalty_score=type("LoyaltyScore", (), {"value": 70})(),
                tags=(),
            ),
        ]
        self.rate_limiter = InMemoryRateLimiter()
        self.message_sender = InMemoryMessageSender()
        self.use_case = SendBulkMessageUseCase(
            segment_repository=InMemorySegmentRepository(self.segment),
            contact_repository=InMemoryContactRepository(self.contacts),
            rate_limiter=self.rate_limiter,
            message_sender=self.message_sender,
        )

    def test_sends_template_to_each_matching_contact(self):
        result = self.use_case.execute(
            segment_id=self.segment.id,
            template="Bonjour {prenom}, merci pour votre achat.",
            channel="whatsapp",
        )

        self.assertEqual(result["status"], "processing")
        self.assertEqual(result["recipient_count"], 2)
        self.assertEqual(len(self.message_sender.sent), 2)
        self.assertEqual(self.rate_limiter.calls, ["whatsapp", "whatsapp"])
        self.assertEqual(
            {message[0] for message in self.message_sender.sent},
            {"whatsapp"},
        )


if __name__ == "__main__":
    unittest.main()

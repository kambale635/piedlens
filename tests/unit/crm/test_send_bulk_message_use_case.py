import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.use_cases.send_bulk_message_use_case import SendBulkMessageUseCase
from contexts.crm.application.use_cases.process_bulk_message_campaign_use_case import (
    BulkMessageDeliveryResult,
    ProcessBulkMessageCampaignUseCase,
)
from contexts.crm.domain.events.crm_events import BulkMessageCompleted, BulkMessageQueued
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.domain.entities.segment import CRMSegment
from contexts.crm.domain.value_objects.segment_rule import SegmentRule
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

    def find_by_id(self, contact_id):
        return next((contact for contact in self.contacts if contact.id == contact_id), None)


class InMemoryRateLimiter:
    def __init__(self):
        self.calls = []
        self.allowed = True

    def check_allowed(self, channel):
        self.calls.append(channel)
        return self.allowed


class InMemoryMessageSender:
    def __init__(self):
        self.sent = []

    def send_message(self, channel, contact, template, idempotency_key):
        self.sent.append((channel, contact.id, template, idempotency_key))
        return BulkMessageDeliveryResult(succeeded=True)


class InMemoryCampaignRepository:
    def __init__(self):
        self.campaigns = {}
        self.recipients = {}

    def create(self, campaign):
        self.campaigns[campaign.id] = campaign
        self.recipients[campaign.id] = {
            contact_id: "queued" for contact_id in campaign.recipient_contact_ids
        }

    def find_by_id(self, campaign_id):
        return self.campaigns.get(campaign_id)

    def find_pending_contact_ids(self, campaign_id):
        return [
            contact_id
            for contact_id, status in self.recipients[campaign_id].items()
            if status == "queued"
        ]

    def mark_sent(self, campaign_id, contact_id):
        self.recipients[campaign_id][contact_id] = "sent"

    def mark_failed(self, campaign_id, contact_id, failure_code):
        self.recipients[campaign_id][contact_id] = "failed"

    def counts(self, campaign_id):
        statuses = list(self.recipients[campaign_id].values())
        return statuses.count("sent"), statuses.count("failed"), statuses.count("queued")

    def complete(self, campaign_id):
        campaign = self.campaigns[campaign_id]
        campaign.complete(self.counts(campaign_id)[2])
        return campaign


class InMemoryProcessedEvents:
    def __init__(self):
        self.processed = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.processed

    def mark_processed(self, event_id, consumer_name):
        self.processed.add((event_id, consumer_name))


class InMemoryUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class InMemoryOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


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
        self.campaign_repository = InMemoryCampaignRepository()
        self.outbox = InMemoryOutbox()
        self.unit_of_work = InMemoryUnitOfWork()
        self.use_case = SendBulkMessageUseCase(
            segment_repository=InMemorySegmentRepository(self.segment),
            contact_repository=InMemoryContactRepository(self.contacts),
            campaign_repository=self.campaign_repository,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

    def test_creates_durable_campaign_and_outbox_without_sending_inline(self):
        result = self.use_case.execute(
            segment_id=self.segment.id,
            template="Bonjour {prenom}, merci pour votre achat.",
            channel="whatsapp",
        )

        self.assertEqual(result.status, "processing")
        self.assertEqual(result.recipient_count, 2)
        self.assertEqual(len(self.message_sender.sent), 0)
        self.assertEqual(self.campaign_repository.counts(result.bulk_message_log_id), (0, 0, 2))
        self.assertIsInstance(self.outbox.events[0], BulkMessageQueued)

    def test_worker_sends_recipients_and_finalizes_outbox_once(self):
        queued = self.use_case.execute(
            segment_id=self.segment.id,
            template="Pre-rendered text",
            channel="whatsapp",
        )
        queue_event = self.outbox.events[0]
        processed = InMemoryProcessedEvents()
        worker = ProcessBulkMessageCampaignUseCase(
            campaign_repository=self.campaign_repository,
            contact_repository=InMemoryContactRepository(self.contacts),
            processed_events=processed,
            rate_limiter=self.rate_limiter,
            message_sender=self.message_sender,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

        result = worker.execute(queue_event.event_id, queued.bulk_message_log_id)
        replay = worker.execute(queue_event.event_id, queued.bulk_message_log_id)

        self.assertEqual((result.status, result.sent_count, result.pending_count), ("completed", 2, 0))
        self.assertEqual(replay, result)
        self.assertEqual(len(self.message_sender.sent), 2)
        self.assertTrue(all(message[3].startswith(f"{queued.bulk_message_log_id}:") for message in self.message_sender.sent))
        self.assertEqual(sum(isinstance(event, BulkMessageCompleted) for event in self.outbox.events), 1)

    def test_rate_limited_campaign_remains_processing_and_can_resume(self):
        queued = self.use_case.execute(
            segment_id=self.segment.id,
            template="Pre-rendered text",
            channel="instagram",
        )
        queue_event = self.outbox.events[0]
        processed = InMemoryProcessedEvents()
        self.rate_limiter.allowed = False
        worker = ProcessBulkMessageCampaignUseCase(
            campaign_repository=self.campaign_repository,
            contact_repository=InMemoryContactRepository(self.contacts),
            processed_events=processed,
            rate_limiter=self.rate_limiter,
            message_sender=self.message_sender,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
        )

        first = worker.execute(queue_event.event_id, queued.bulk_message_log_id)
        self.assertEqual((first.status, first.pending_count), ("processing", 2))
        self.rate_limiter.allowed = True
        second = worker.execute(queue_event.event_id, queued.bulk_message_log_id)

        self.assertEqual((second.status, second.sent_count, second.pending_count), ("completed", 2, 0))


if __name__ == "__main__":
    unittest.main()

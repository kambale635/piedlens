import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.crm.application.use_cases.send_bulk_message_use_case import SendBulkMessageUseCase
from contexts.crm.application.use_cases.send_bulk_message_use_case import (
    MarketingConfirmationRequiredException,
)
from contexts.crm.application.use_cases.process_bulk_message_campaign_use_case import (
    BulkMessageDeliveryResult,
    ProcessBulkMessageCampaignUseCase,
)
from contexts.crm.domain.events.crm_events import BulkMessageCompleted, BulkMessageQueued
from contexts.crm.domain.entities.contact import Contact
from contexts.crm.domain.entities.segment import CRMSegment
from contexts.crm.domain.value_objects.segment_rule import SegmentRule
from shared_kernel.value_objects.money import Money
from shared_kernel.application_exceptions import PlanUpgradeRequiredException


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

    def mark_manual_link(self, campaign_id, contact_id):
        self.recipients[campaign_id][contact_id] = "manual_link"

    def mark_failed(self, campaign_id, contact_id, failure_code):
        self.recipients[campaign_id][contact_id] = "failed"

    def counts(self, campaign_id):
        statuses = list(self.recipients[campaign_id].values())
        return (
            statuses.count("sent"),
            statuses.count("failed"),
            statuses.count("queued"),
            statuses.count("manual_link"),
        )

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


class InMemoryEntitlements:
    def entitlements_for(self, merchant_id):
        return {
            "bulk_messages": True,
            "reminder_modes": ["manual_link", "api_send"],
        }


class InMemoryOutboundUsage:
    def __init__(self):
        self.reservations = []

    def reserve(self, merchant_id, category, count):
        self.reservations.append((merchant_id, category, count))
        return {"count": count}

    def usage_for(self, merchant_id):
        return []


class InMemoryCostEstimator:
    def estimate(self, country, currency, category, count):
        return {
            "unitAmountMinor": 3,
            "amountMinor": 3 * count,
            "currency": currency,
            "numberOfMessages": count,
            "chargeProcessor": "meta_direct",
        }


class FixedMerchantCountry:
    def country_code_for(self, merchant_id):
        return "US"


class FixedMerchantCurrency:
    def currency_for(self, merchant_id):
        return "USD"


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
                external_identifier="14155550101",
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
                external_identifier="14155550102",
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
        self.outbound_usage = InMemoryOutboundUsage()
        self.use_case = SendBulkMessageUseCase(
            segment_repository=InMemorySegmentRepository(self.segment),
            contact_repository=InMemoryContactRepository(self.contacts),
            campaign_repository=self.campaign_repository,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            entitlements=InMemoryEntitlements(),
            cost_estimator=InMemoryCostEstimator(),
            merchant_country_reader=FixedMerchantCountry(),
            merchant_currency_reader=FixedMerchantCurrency(),
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
        self.assertEqual(self.campaign_repository.counts(result.bulk_message_log_id), (0, 0, 2, 0))
        self.assertIsInstance(self.outbox.events[0], BulkMessageQueued)

    def test_rejects_bulk_campaign_without_plan_entitlement(self):
        class NoBulkEntitlements:
            def entitlements_for(self, merchant_id):
                return {"bulk_messages": False}

        self.use_case._entitlements = NoBulkEntitlements()

        with self.assertRaises(PlanUpgradeRequiredException) as raised:
            self.use_case.execute(self.segment.id, "message", "whatsapp", self.merchant_id)

        self.assertEqual(raised.exception.status_code, 402)
        self.assertEqual(raised.exception.entitlement_key, "bulk_messages")

    def test_manual_link_returns_wa_me_links_without_reserving_or_sending(self):
        result = self.use_case.execute(
            self.segment.id, "Hello there", "whatsapp", self.merchant_id
        )

        self.assertEqual(len(result.manual_links), 2)
        self.assertIn("https://wa.me/", result.manual_links[0]["url"])
        self.assertEqual(self.outbound_usage.reservations, [])
        self.assertEqual(self.message_sender.sent, [])

    def test_manual_link_worker_proposes_recipients_without_sending(self):
        queued = self.use_case.execute(
            self.segment.id, "Manual follow-up", "whatsapp", self.merchant_id
        )
        queue_event = self.outbox.events[0]
        worker = ProcessBulkMessageCampaignUseCase(
            campaign_repository=self.campaign_repository,
            contact_repository=InMemoryContactRepository(self.contacts),
            processed_events=InMemoryProcessedEvents(),
            rate_limiter=self.rate_limiter,
            message_sender=self.message_sender,
            unit_of_work=self.unit_of_work,
            outbox=self.outbox,
            outbound_usage=self.outbound_usage,
        )

        result = worker.execute(queue_event.event_id, queued.bulk_message_log_id)

        self.assertEqual(result.proposed_count, 2)
        self.assertEqual(self.message_sender.sent, [])
        self.assertEqual(self.outbound_usage.reservations, [])

    def test_api_campaign_with_empty_audience_does_not_estimate_or_reserve(self):
        empty_segment = CRMSegment.create(
            merchant_id=self.merchant_id,
            name="Empty",
            definition_rule=SegmentRule(field="order_count", operator=">", value=100),
        )
        self.use_case._segment_repository = InMemorySegmentRepository(empty_segment)

        result = self.use_case.execute(
            empty_segment.id,
            "Utility notice",
            "whatsapp",
            self.merchant_id,
            delivery_mode="api_send",
            category="utility",
        )

        self.assertEqual(result.recipient_count, 0)
        self.assertIsNone(result.cost_estimate)
        self.assertEqual(self.outbound_usage.reservations, [])

    def test_api_marketing_requires_confirmed_cost_then_reserves_usage(self):
        with self.assertRaises(MarketingConfirmationRequiredException):
            self.use_case.execute(
                self.segment.id,
                "Promo",
                "whatsapp",
                self.merchant_id,
                delivery_mode="api_send",
                category="marketing",
            )

        estimate = InMemoryCostEstimator().estimate("US", "USD", "marketing", 2)
        result = self.use_case.execute(
            self.segment.id,
            "Promo",
            "whatsapp",
            self.merchant_id,
            delivery_mode="api_send",
            category="marketing",
            marketing_confirmed=True,
            confirmed_estimate=estimate,
        )

        self.assertEqual(result.cost_estimate, estimate)
        self.assertEqual(self.outbound_usage.reservations, [])

    def test_worker_sends_recipients_and_finalizes_outbox_once(self):
        queued = self.use_case.execute(
            segment_id=self.segment.id,
            template="Pre-rendered text",
            channel="whatsapp",
            delivery_mode="api_send",
            category="utility",
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
            outbound_usage=self.outbound_usage,
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
            delivery_mode="api_send",
            category="utility",
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
            outbound_usage=self.outbound_usage,
        )

        first = worker.execute(queue_event.event_id, queued.bulk_message_log_id)
        self.assertEqual((first.status, first.pending_count), ("processing", 2))
        self.rate_limiter.allowed = True
        second = worker.execute(queue_event.event_id, queued.bulk_message_log_id)

        self.assertEqual((second.status, second.sent_count, second.pending_count), ("completed", 2, 0))


if __name__ == "__main__":
    unittest.main()

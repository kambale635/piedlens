from datetime import datetime, timezone
from uuid import uuid4

from django.test import TestCase

from contexts.crm.application.use_cases.purge_merchant_data_use_case import PurgeMerchantDataUseCase
from contexts.crm.infrastructure.messaging.merchant_data_deletion_handler import handle_merchant_data_deleted
from contexts.crm.infrastructure.persistence.models import (
    BulkMessageCampaignRecord,
    BulkMessageRecipientRecord,
    ContactRecord,
    MerchantDeletionProgressRecord,
    OutboxEventRecord,
    ProcessedMessageRecord,
    RelationshipAnomalyNotificationRecord,
    SegmentRecord,
)


class CRMMerchantDataDeletionTests(TestCase):
    def test_purge_removes_all_owned_data_and_preserves_other_merchants(self):
        merchant_id = uuid4()
        other_merchant_id = uuid4()
        event_id = uuid4()
        now = datetime(2026, 10, 18, tzinfo=timezone.utc)
        contact = ContactRecord.objects.create(
            merchant_id=merchant_id, platform_connection_id=uuid4(), external_identifier="target",
            display_name="Target", total_spent_by_currency={"EUR": "10"}, order_count=1,
            last_interaction_at=now, purchase_history=[{"order_id": str(uuid4())}],
        )
        other_contact = ContactRecord.objects.create(
            merchant_id=other_merchant_id, platform_connection_id=uuid4(), external_identifier="other",
            display_name="Other", total_spent_by_currency={}, order_count=0,
            last_interaction_at=now,
        )
        segment = SegmentRecord.objects.create(
            merchant_id=merchant_id, name="Target", rule_field="order_count",
            rule_operator="gt", rule_value=0,
        )
        other_segment = SegmentRecord.objects.create(
            merchant_id=other_merchant_id, name="Other", rule_field="order_count",
            rule_operator="gt", rule_value=0,
        )
        campaign = BulkMessageCampaignRecord.objects.create(
            merchant_id=merchant_id, segment_id=segment.id, channel="whatsapp",
            template="Hello {{name}}", status="completed", recipient_count=1, created_at=now,
        )
        other_campaign = BulkMessageCampaignRecord.objects.create(
            merchant_id=other_merchant_id, segment_id=other_segment.id, channel="whatsapp",
            template="Other", status="completed", recipient_count=1, created_at=now,
        )
        recipient = BulkMessageRecipientRecord.objects.create(
            campaign_id=campaign.id, contact_id=contact.id, status="sent", sent_at=now,
        )
        other_recipient = BulkMessageRecipientRecord.objects.create(
            campaign_id=other_campaign.id, contact_id=other_contact.id, status="sent", sent_at=now,
        )
        notification = RelationshipAnomalyNotificationRecord.objects.create(
            merchant_id=merchant_id, contact_id=contact.id, last_purchase_order_id=uuid4(),
            days_since_last_purchase=60, usual_interval_days=30, notified_at=now,
        )
        other_notification = RelationshipAnomalyNotificationRecord.objects.create(
            merchant_id=other_merchant_id, contact_id=other_contact.id,
            last_purchase_order_id=uuid4(), days_since_last_purchase=60,
            usual_interval_days=30, notified_at=now,
        )
        envelope = {
            "eventId": str(event_id), "eventType": "MerchantDataDeleted",
            "producedBy": "backup", "payload": {"merchant_id": str(merchant_id)},
        }

        self.assertTrue(handle_merchant_data_deleted(envelope))
        self.assertFalse(handle_merchant_data_deleted(envelope))

        self.assertFalse(ContactRecord.objects.filter(id=contact.id).exists())
        self.assertFalse(SegmentRecord.objects.filter(id=segment.id).exists())
        self.assertFalse(BulkMessageRecipientRecord.objects.filter(id=recipient.id).exists())
        self.assertFalse(BulkMessageCampaignRecord.objects.filter(id=campaign.id).exists())
        self.assertFalse(RelationshipAnomalyNotificationRecord.objects.filter(id=notification.id).exists())
        self.assertTrue(ContactRecord.objects.filter(id=other_contact.id).exists())
        self.assertTrue(SegmentRecord.objects.filter(id=other_segment.id).exists())
        self.assertTrue(BulkMessageRecipientRecord.objects.filter(id=other_recipient.id).exists())
        self.assertTrue(BulkMessageCampaignRecord.objects.filter(id=other_campaign.id).exists())
        self.assertTrue(RelationshipAnomalyNotificationRecord.objects.filter(id=other_notification.id).exists())
        self.assertEqual(
            ProcessedMessageRecord.objects.filter(
                event_id=event_id, consumer_name=PurgeMerchantDataUseCase.CONSUMER_NAME
            ).count(),
            1,
        )
        self.assertEqual(
            OutboxEventRecord.objects.filter(
                event_type="MerchantDataPurged", payload__context="crm",
                payload__merchant_id=str(merchant_id),
            ).count(),
            1,
        )
        self.assertEqual(MerchantDeletionProgressRecord.objects.filter(event_id=event_id).count(), 5)
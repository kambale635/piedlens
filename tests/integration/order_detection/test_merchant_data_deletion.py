from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase

from contexts.order_detection.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase,
)
from contexts.order_detection.infrastructure.messaging.merchant_data_deletion_handler import (
    handle_merchant_data_deleted,
)
from contexts.order_detection.infrastructure.persistence.models import (
    ContactReferenceRedirectRecord,
    DetectionCandidateRecord,
    MerchantDeletionProgressRecord,
    OrderRecord,
    OutboxEventRecord,
    ProcessedEventRecord,
    ReminderRecord,
)


class OrderDetectionMerchantDataDeletionTests(TestCase):
    def test_purge_removes_merchant_records_without_touching_other_merchants(self):
        merchant_id = uuid4()
        other_merchant_id = uuid4()
        event_id = uuid4()
        now = datetime(2026, 10, 18, tzinfo=timezone.utc)
        order = OrderRecord.objects.create(
            merchant_id=merchant_id, contact_id=uuid4(), detected_amount=Decimal("20.00"),
            currency="EUR", confidence_score=90, source_message_ids=[str(uuid4())],
            status="pending_payment", created_at=now, last_status_change_at=now,
        )
        other_order = OrderRecord.objects.create(
            merchant_id=other_merchant_id, contact_id=uuid4(), detected_amount=Decimal("30.00"),
            currency="EUR", confidence_score=90, source_message_ids=[str(uuid4())],
            status="pending_payment", created_at=now, last_status_change_at=now,
        )
        reminder = ReminderRecord.objects.create(
            order_id=order.id, reminder_type="payment_pending", status="scheduled",
            scheduled_for=now,
        )
        other_reminder = ReminderRecord.objects.create(
            order_id=other_order.id, reminder_type="payment_pending", status="scheduled",
            scheduled_for=now,
        )
        candidate = DetectionCandidateRecord.objects.create(
            merchant_id=merchant_id, contact_id=uuid4(), detected_amount=Decimal("12.00"),
            currency="EUR", confidence_score=50, source_message_id=uuid4(),
            status="pending_review", created_at=now,
        )
        other_candidate = DetectionCandidateRecord.objects.create(
            merchant_id=other_merchant_id, contact_id=uuid4(), detected_amount=Decimal("15.00"),
            currency="EUR", confidence_score=50, source_message_id=uuid4(),
            status="pending_review", created_at=now,
        )
        redirect = ContactReferenceRedirectRecord.objects.create(
            merged_contact_id=uuid4(), merchant_id=merchant_id, primary_contact_id=uuid4(),
        )
        other_redirect = ContactReferenceRedirectRecord.objects.create(
            merged_contact_id=uuid4(), merchant_id=other_merchant_id, primary_contact_id=uuid4(),
        )
        envelope = {
            "eventId": str(event_id), "eventType": "MerchantDataDeleted",
            "producedBy": "backup", "payload": {"merchant_id": str(merchant_id)},
        }

        self.assertTrue(handle_merchant_data_deleted(envelope))
        self.assertEqual(
            list(ProcessedEventRecord.objects.values("event_id", "consumer_name")),
            [{"event_id": event_id, "consumer_name": PurgeMerchantDataUseCase.CONSUMER_NAME}],
        )
        self.assertFalse(handle_merchant_data_deleted(envelope))

        self.assertFalse(OrderRecord.objects.filter(id=order.id).exists())
        self.assertFalse(DetectionCandidateRecord.objects.filter(id=candidate.id).exists())
        self.assertFalse(ReminderRecord.objects.filter(id=reminder.id).exists())
        self.assertFalse(ContactReferenceRedirectRecord.objects.filter(merged_contact_id=redirect.merged_contact_id).exists())
        self.assertTrue(OrderRecord.objects.filter(id=other_order.id).exists())
        self.assertTrue(DetectionCandidateRecord.objects.filter(id=other_candidate.id).exists())
        self.assertTrue(ReminderRecord.objects.filter(id=other_reminder.id).exists())
        self.assertTrue(ContactReferenceRedirectRecord.objects.filter(merged_contact_id=other_redirect.merged_contact_id).exists())
        self.assertEqual(
            ProcessedEventRecord.objects.filter(
                event_id=event_id, consumer_name=PurgeMerchantDataUseCase.CONSUMER_NAME
            ).count(),
            1,
            list(ProcessedEventRecord.objects.values("event_id", "consumer_name")),
        )
        self.assertEqual(
            OutboxEventRecord.objects.filter(
                event_type="MerchantDataPurged", payload__context="order-detection",
                payload__merchant_id=str(merchant_id),
            ).count(),
            1,
        )
        self.assertEqual(MerchantDeletionProgressRecord.objects.filter(event_id=event_id).count(), 4)
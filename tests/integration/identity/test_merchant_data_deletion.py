from uuid import uuid4

from django.test import TestCase

from contexts.identity.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase,
)
from contexts.identity.infrastructure.persistence.models import (
    MerchantRecord,
    OutboxEventRecord,
    ProcessedEventRecord,
    UserRecord,
)
from contexts.identity.infrastructure.messaging.merchant_data_deletion_handler import (
    handle_merchant_data_deleted,
)


class IdentityMerchantDataDeletionTests(TestCase):
    def test_purge_deletes_merchant_retains_user_and_is_idempotent(self):
        user_id = uuid4()
        merchant_id = uuid4()
        event_id = uuid4()
        UserRecord.objects.create(
            id=user_id,
            phone_number="+14155550124",
            password_hash="encoded",
            created_at="2026-10-18T00:00:00Z",
        )
        MerchantRecord.objects.create(
            id=merchant_id,
            name="Acme",
            country="FR",
            preferred_language="fr",
            currency="EUR",
            subscription_plan="starter",
            created_at="2026-10-18T00:00:00Z",
        )

        envelope = {
            "eventId": str(event_id),
            "eventType": "MerchantDataDeleted",
            "producedBy": "backup",
            "payload": {"merchant_id": str(merchant_id)},
        }
        handle_merchant_data_deleted(envelope)
        handle_merchant_data_deleted(envelope)

        self.assertFalse(MerchantRecord.objects.filter(id=merchant_id).exists())
        self.assertTrue(UserRecord.objects.filter(id=user_id).exists())
        self.assertEqual(
            ProcessedEventRecord.objects.filter(
                event_id=event_id,
                consumer_name=PurgeMerchantDataUseCase.CONSUMER_NAME,
            ).count(),
            1,
        )
        completion_events = OutboxEventRecord.objects.filter(
            event_type="MerchantDataPurged",
            payload__context="identity",
            payload__merchant_id=str(merchant_id),
        )
        self.assertEqual(completion_events.count(), 1)
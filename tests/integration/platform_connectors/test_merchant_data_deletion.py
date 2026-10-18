from datetime import datetime, timezone
from uuid import uuid4

from django.test import TestCase

from contexts.platform_connectors.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase,
)
from contexts.platform_connectors.domain.entities.message import Message
from contexts.platform_connectors.infrastructure.messaging.merchant_data_deletion_handler import (
    handle_merchant_data_deleted,
)
from contexts.platform_connectors.infrastructure.persistence.django_message_repository import (
    DjangoMessageRepository,
)
from contexts.platform_connectors.infrastructure.persistence.models import (
    MerchantDeletionProgressRecord,
    MessageRecord,
    OutboxEventRecord,
    PlatformConnectionRecord,
    ProcessedEventRecord,
)


class PlatformConnectorsMerchantDataDeletionTests(TestCase):
    def test_purge_removes_only_owned_connections_and_messages_and_blocks_late_writes(self):
        merchant_id = uuid4()
        other_merchant_id = uuid4()
        event_id = uuid4()
        connection_id = uuid4()
        other_connection_id = uuid4()
        PlatformConnectionRecord.objects.create(
            id=connection_id,
            merchant_id=merchant_id,
            platform_type="whatsapp",
            external_account_id="target-account",
            encrypted_access_token="encrypted-target-token",
            status="active",
        )
        PlatformConnectionRecord.objects.create(
            id=other_connection_id,
            merchant_id=other_merchant_id,
            platform_type="whatsapp",
            external_account_id="other-account",
            encrypted_access_token="encrypted-other-token",
            status="active",
        )
        target_message = MessageRecord.objects.create(
            platform_connection_id=connection_id,
            merchant_id=merchant_id,
            external_message_id="target-message",
            external_sender_id="sender",
            received_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        )
        other_message = MessageRecord.objects.create(
            platform_connection_id=other_connection_id,
            merchant_id=other_merchant_id,
            external_message_id="other-message",
            external_sender_id="sender",
            received_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        )
        envelope = {
            "eventId": str(event_id),
            "eventType": "MerchantDataDeleted",
            "producedBy": "backup",
            "payload": {"merchant_id": str(merchant_id)},
        }

        handle_merchant_data_deleted(envelope)
        handle_merchant_data_deleted(envelope)

        self.assertFalse(PlatformConnectionRecord.objects.filter(id=connection_id).exists())
        self.assertFalse(MessageRecord.objects.filter(id=target_message.id).exists())
        self.assertTrue(PlatformConnectionRecord.objects.filter(id=other_connection_id).exists())
        self.assertTrue(MessageRecord.objects.filter(id=other_message.id).exists())
        self.assertFalse(
            DjangoMessageRepository().save_if_new(
                Message(
                    id=uuid4(),
                    platform_connection_id=connection_id,
                    merchant_id=merchant_id,
                    external_message_id="late-message",
                    external_sender_id="sender",
                    display_name="",
                    text_content="",
                    received_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
                )
            )
        )
        self.assertEqual(
            ProcessedEventRecord.objects.filter(
                event_id=event_id,
                consumer_name=PurgeMerchantDataUseCase.CONSUMER_NAME,
            ).count(),
            1,
        )
        self.assertEqual(
            OutboxEventRecord.objects.filter(
                event_type="MerchantDataPurged",
                payload__context="platform-connectors",
                payload__merchant_id=str(merchant_id),
            ).count(),
            1,
        )
        self.assertEqual(
            MerchantDeletionProgressRecord.objects.filter(event_id=event_id).count(),
            2,
        )
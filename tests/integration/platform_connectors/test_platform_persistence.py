from datetime import datetime, timezone
from uuid import uuid4

from django.test import TestCase

from contexts.platform_connectors.domain.entities.message import Message
from contexts.platform_connectors.infrastructure.persistence.django_message_repository import (
    DjangoMessageRepository,
)
from contexts.platform_connectors.infrastructure.persistence.models import (
    MessageRecord,
    PlatformConnectionRecord,
)


class PlatformMessagePersistenceTests(TestCase):
    def test_external_message_id_is_unique_per_connection(self):
        connection_id = uuid4()
        merchant_id = uuid4()
        PlatformConnectionRecord.objects.create(
            id=connection_id,
            merchant_id=merchant_id,
            platform_type="whatsapp",
            external_account_id="account-42",
            encrypted_access_token="encrypted",
            status="active",
        )
        message = Message(
            id=uuid4(),
            platform_connection_id=connection_id,
            merchant_id=merchant_id,
            external_message_id="provider-42",
            external_sender_id="sender-9",
            display_name="Customer",
            text_content="hello",
            received_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
        )
        repository = DjangoMessageRepository()

        self.assertTrue(repository.save_if_new(message))
        self.assertFalse(repository.save_if_new(message))
        self.assertEqual(MessageRecord.objects.filter(platform_connection_id=connection_id).count(), 1)
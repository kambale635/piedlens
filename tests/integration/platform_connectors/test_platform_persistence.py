import base64
from io import StringIO
from datetime import datetime, timezone
from uuid import uuid4

from django.test import TestCase, override_settings

from contexts.platform_connectors.domain.entities.message import Message
from contexts.platform_connectors.infrastructure.persistence.django_message_repository import (
    DjangoMessageRepository,
)
from contexts.platform_connectors.infrastructure.adapters.django_backup_message_reader import (
    DjangoBackupMessageReader,
)
from contexts.platform_connectors.infrastructure.persistence.django_platform_outbox import (
    DjangoPlatformConnectorsOutbox,
)
from contexts.platform_connectors.domain.events.platform_events import MessageReceived
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
        stored = MessageRecord.objects.get(platform_connection_id=connection_id)
        self.assertNotEqual(stored.text_content, "hello")
        self.assertTrue(stored.text_content.startswith("v1."))
        self.assertEqual(
            DjangoBackupMessageReader().read_messages(connection_id)[0]["text_content"],
            "hello",
        )

    def test_message_received_outbox_payload_is_encrypted_at_rest(self):
        text = "message-body-outbox-sentinel"
        event = MessageReceived(
            merchant_id=uuid4(),
            platform_connection_id=uuid4(),
            message_id=uuid4(),
            external_message_id="external-1",
            external_sender_id="sender-1",
            display_name="Customer",
            text_content=text,
            received_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
        )

        DjangoPlatformConnectorsOutbox().add(event)
        from contexts.platform_connectors.infrastructure.persistence.models import OutboxEventRecord

        stored = OutboxEventRecord.objects.get(event_id=event.event_id)
        self.assertNotIn(text, str(stored.payload))
        self.assertTrue(stored.payload["text_content"].startswith("v1."))

    def test_message_content_rotation_reencrypts_legacy_rows_and_outbox(self):
        from django.core.management import call_command
        from contexts.platform_connectors.infrastructure.persistence.models import OutboxEventRecord

        connection_id = uuid4()
        merchant_id = uuid4()
        PlatformConnectionRecord.objects.create(
            id=connection_id,
            merchant_id=merchant_id,
            platform_type="whatsapp",
            external_account_id="legacy-account",
            encrypted_access_token="encrypted",
            status="active",
        )
        MessageRecord.objects.create(
            id=uuid4(),
            platform_connection_id=connection_id,
            merchant_id=merchant_id,
            external_message_id="legacy-message",
            external_sender_id="sender",
            text_content="legacy-message-text",
            received_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
        )
        event = OutboxEventRecord.objects.create(
            event_id=uuid4(),
            event_type="MessageReceived",
            occurred_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
            payload={"text_content": "legacy-outbox-text"},
        )
        first_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        second_key = base64.urlsafe_b64encode(b"b" * 32).decode()
        output = StringIO()

        with override_settings(
            PLATFORM_MESSAGE_ENCRYPTION_KEYS={"v1": first_key, "v2": second_key},
            PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION="v2",
        ):
            call_command("rotate_platform_message_content", stdout=output)

        message = MessageRecord.objects.get(external_message_id="legacy-message")
        event.refresh_from_db()
        self.assertTrue(message.text_content.startswith("v2."))
        self.assertTrue(event.payload["text_content"].startswith("v2."))
        self.assertNotIn("legacy-message-text", message.text_content)
        self.assertNotIn("legacy-outbox-text", str(event.payload))
        self.assertEqual(output.getvalue(), "Rotated 2 message content value(s).\n")
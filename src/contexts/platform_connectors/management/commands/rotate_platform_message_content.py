from django.core.management.base import BaseCommand
from django.db import transaction

from contexts.platform_connectors.infrastructure.adapters.django_message_content_cipher import (
    DjangoMessageContentCipher,
)
from contexts.platform_connectors.infrastructure.persistence.models import (
    MessageRecord,
    OutboxEventRecord,
)


class Command(BaseCommand):
    """Re-encrypt stored message rows and unpublished MessageReceived Outbox payloads."""

    help = "Rotate persisted message content to the active versioned encryption key."

    def handle(self, *args, **options):
        """Re-encrypt messages and event payloads in independent transactions."""
        cipher = DjangoMessageContentCipher()
        rotated = 0
        message_ids = list(MessageRecord.objects.order_by("id").values_list("id", flat=True))
        for message_id in message_ids:
            with transaction.atomic():
                message = MessageRecord.objects.select_for_update().get(id=message_id)
                if cipher.key_version(message.text_content) == cipher.active_version:
                    continue
                message.text_content = cipher.encrypt(cipher.decrypt(message.text_content))
                message.save(update_fields=["text_content"])
                rotated += 1

        event_ids = list(
            OutboxEventRecord.objects.filter(event_type="MessageReceived")
            .order_by("event_id")
            .values_list("event_id", flat=True)
        )
        for event_id in event_ids:
            with transaction.atomic():
                event = OutboxEventRecord.objects.select_for_update().get(event_id=event_id)
                text = event.payload.get("text_content", "")
                if cipher.key_version(text) == cipher.active_version:
                    continue
                event.payload = {
                    **event.payload,
                    "text_content": cipher.encrypt(cipher.decrypt(text)),
                }
                event.save(update_fields=["payload"])
                rotated += 1
        self.stdout.write(f"Rotated {rotated} message content value(s).")
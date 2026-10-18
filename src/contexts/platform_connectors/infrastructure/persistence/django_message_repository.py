from ...domain.entities.message import Message
from .models import MessageRecord, PlatformConnectionRecord


class DjangoMessageRepository:
    """Persist normalized messages idempotently using the database uniqueness key (INV-PC-03)."""

    def save_if_new(self, message: Message) -> bool:
        """Return true only for the first message with this connection/external ID pair."""
        connection_exists = PlatformConnectionRecord.objects.select_for_update().filter(
            id=message.platform_connection_id,
            merchant_id=message.merchant_id,
        ).exists()
        if not connection_exists:
            return False
        _, created = MessageRecord.objects.get_or_create(
            platform_connection_id=message.platform_connection_id,
            external_message_id=message.external_message_id,
            defaults={
                "id": message.id,
                "merchant_id": message.merchant_id,
                "external_sender_id": message.external_sender_id,
                "display_name": message.display_name,
                "text_content": message.text_content,
                "received_at": message.received_at,
            },
        )
        return created
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ...domain.entities.message import Message


class MockWebhookPayloadMapper:
    """Translate the documented mock webhook envelope to normalized messages."""

    def map_messages(self, connection, payload: dict) -> list[Message]:
        """Map only known message fields; provider-specific data remains in this adapter."""
        messages = []
        for item in payload.get("messages", []):
            timestamp = item.get("timestamp")
            received_at = (
                datetime.fromtimestamp(int(timestamp), timezone.utc)
                if timestamp is not None
                else datetime.now(timezone.utc)
            )
            messages.append(
                Message(
                    id=uuid4(),
                    platform_connection_id=connection.id,
                    merchant_id=connection.merchant_id,
                    external_message_id=str(item["id"]),
                    external_sender_id=str(item["from"]),
                    display_name=str(item.get("displayName", "")),
                    text_content=str(item.get("text", "")),
                    received_at=received_at,
                )
            )
        return messages

    def normalize(self, connection, payload: dict) -> list[Message]:
        """Expose the mapper through the registry's capability-oriented contract."""
        return self.map_messages(connection, payload)
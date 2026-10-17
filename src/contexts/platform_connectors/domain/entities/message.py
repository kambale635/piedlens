from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Message:
    """Normalized inbound message with no platform-specific payload fields (INV-PC-03)."""

    id: UUID
    platform_connection_id: UUID
    merchant_id: UUID
    external_message_id: str
    external_sender_id: str
    display_name: str
    text_content: str
    received_at: datetime
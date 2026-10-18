from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class PlatformConnected:
    """Outbox event emitted after a connection and encrypted token are persisted."""

    merchant_id: UUID
    connection_id: UUID
    platform_type: str
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class PlatformConnectionExpired:
    """Outbox event emitted after token refresh permanently expires a connection."""

    merchant_id: UUID
    connection_id: UUID
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MessageReceived:
    """Normalized message event shared with CRM and Rules Engine consumers."""

    merchant_id: UUID
    platform_connection_id: UUID
    message_id: UUID
    external_message_id: str
    external_sender_id: str
    display_name: str
    text_content: str
    received_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MerchantDataPurged:
    """Platform Connectors confirmation that local credentials and messages were purged (INV-PC-05)."""

    context: str
    merchant_id: UUID
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class BackupCompleted:
    """Outbox event for a complete immutable snapshot."""

    merchant_id: UUID
    snapshot_id: UUID
    platform_connection_id: UUID
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class BackupFailed:
    """Outbox event indicating the snapshot failed without exposing data content."""

    merchant_id: UUID
    snapshot_id: UUID
    platform_connection_id: UUID
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AccountHealthAlertRaised:
    """Outbox alert for a connection that may be at risk or suspended."""

    platform_connection_id: UUID
    health_status: str
    signals: tuple[str, ...]
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MerchantDataDeleted:
    """Outbox request for other bounded contexts to purge their own merchant data."""

    merchant_id: UUID
    deleted_at: datetime
    event_id: UUID = field(default_factory=uuid4)
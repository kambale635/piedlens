from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from ..value_objects.snapshot_status import SnapshotStatus


@dataclass(frozen=True)
class BackupSnapshot:
    """Immutable snapshot record; successful snapshots are never edited (INV-BK-01/02)."""

    id: UUID
    merchant_id: UUID
    platform_connection_id: UUID
    snapshot_date: datetime
    status: SnapshotStatus
    data_integrity_hash: str
    storage_reference: str | None
    message_count: int
    media_count: int

    @classmethod
    def succeeded(
        cls, merchant_id, connection_id, snapshot_date, integrity_hash,
        storage_reference, message_count, media_count=0,
    ) -> "BackupSnapshot":
        """Create a complete immutable success only after storage finishes."""
        return cls(
            uuid4(), merchant_id, connection_id, snapshot_date,
            SnapshotStatus.SUCCEEDED, integrity_hash, storage_reference,
            message_count, media_count,
        )

    @classmethod
    def failed(cls, merchant_id, connection_id, snapshot_date) -> "BackupSnapshot":
        """Create a failed terminal record with no partial storage reference (INV-BK-02)."""
        return cls(
            uuid4(), merchant_id, connection_id, snapshot_date,
            SnapshotStatus.FAILED, "", None, 0, 0,
        )
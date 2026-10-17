import hashlib
import json
from uuid import UUID

from shared_kernel.application_exceptions import ResourceNotFoundException
from shared_kernel.ports import (
    IBackupContactReader,
    IBackupMessageReader,
    IConnectionConsentReader,
)

from ...domain.entities.backup_snapshot import BackupSnapshot
from ...domain.events.backup_events import BackupCompleted, BackupFailed
from ..exceptions import BackupConsentRequiredException
from ..ports.backup_ports import (
    IBackupClock,
    IBackupOutbox,
    IBackupRepository,
    IBackupUnitOfWork,
    IObjectStorage,
)


class CreateSnapshotUseCase:
    """Create an incremental, consented snapshot and hash its canonical data (INV-BK-02/03).

    Contract: docs/15-use-cases-catalog.md#contexte-backup.
    Successful snapshots are inserted once and immutable (INV-BK-01); failed reads or
    storage never produce a partial record marked succeeded (INV-BK-02).
    """

    def __init__(
        self,
        backups: IBackupRepository,
        storage: IObjectStorage,
        consent_reader: IConnectionConsentReader,
        message_reader: IBackupMessageReader,
        contact_reader: IBackupContactReader,
        unit_of_work: IBackupUnitOfWork,
        outbox: IBackupOutbox,
        clock: IBackupClock,
    ) -> None:
        """Receive Backup persistence and shared owner-context data ports."""
        self._backups = backups
        self._storage = storage
        self._consent_reader = consent_reader
        self._message_reader = message_reader
        self._contact_reader = contact_reader
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(self, platform_connection_id: UUID) -> dict:
        """Persist one all-or-failed snapshot, reading only consented incremental data."""
        owner = self._consent_reader.consent_for(platform_connection_id)
        if owner is None:
            raise ResourceNotFoundException("Platform connection was not found.")
        merchant_id, consent_given_at = owner
        if consent_given_at is None:
            raise BackupConsentRequiredException("Explicit backup consent is required.")

        previous = self._backups.find_latest_successful(platform_connection_id)
        since = previous.snapshot_date if previous else None
        now = self._clock.now_utc()
        reference = None
        try:
            data = {
                "messages": self._message_reader.read_messages(platform_connection_id, since),
                "contacts": self._contact_reader.read_contacts(
                    merchant_id, platform_connection_id, since
                ),
            }
            encoded = json.dumps(
                data,
                sort_keys=True,
                separators=(",", ":"),
                default=lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value),
            )
            integrity_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            reference = self._storage.store(data)
            snapshot = BackupSnapshot.succeeded(
                merchant_id=merchant_id,
                connection_id=platform_connection_id,
                snapshot_date=now,
                integrity_hash=integrity_hash,
                storage_reference=reference,
                message_count=len(data["messages"]),
                media_count=0,
            )
            event = BackupCompleted(
                merchant_id=merchant_id,
                snapshot_id=snapshot.id,
                platform_connection_id=platform_connection_id,
                occurred_at=now,
            )
        except Exception:
            snapshot = BackupSnapshot.failed(merchant_id, platform_connection_id, now)
            event = BackupFailed(
                merchant_id=merchant_id,
                snapshot_id=snapshot.id,
                platform_connection_id=platform_connection_id,
                occurred_at=now,
            )
            if reference is not None:
                self._storage.delete(reference)
        with self._unit_of_work:
            self._backups.save_snapshot(snapshot)
            self._outbox.add(event)
        return {
            "snapshot_id": snapshot.id,
            "status": snapshot.status.value,
            "message_count": snapshot.message_count,
            "media_count": snapshot.media_count,
        }
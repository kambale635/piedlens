import csv
import io
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from shared_kernel.application_exceptions import ResourceNotFoundException

from ..exceptions import BackupSnapshotNotFoundException
from ..ports.backup_ports import IBackupClock, IBackupRepository, IBackupUnitOfWork, IObjectStorage


class RestoreFromSnapshotUseCase:
    """Build a re-importable JSON and readable CSV export from a successful snapshot.

    Contract: docs/15-use-cases-catalog.md#contexte-backup.
    The export uses an expiring signed URL; no source context is read during restore.
    """

    def __init__(
        self,
        backups: IBackupRepository,
        storage: IObjectStorage,
        unit_of_work: IBackupUnitOfWork,
        clock: IBackupClock,
        export_ttl_minutes: int,
    ) -> None:
        """Receive snapshot, object storage, transaction, time and configured TTL ports."""
        self._backups = backups
        self._storage = storage
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._export_ttl_minutes = export_ttl_minutes

    def execute(
        self,
        platform_connection_id: UUID,
        as_of_date=None,
        merchant_id=None,
    ) -> dict:
        """Prepare an export from the latest successful snapshot not after the requested date."""
        if as_of_date is None:
            snapshot = self._backups.find_latest_successful(platform_connection_id)
        else:
            candidates = self._backups.find_by_date_range(
                platform_connection_id,
                datetime.min.replace(tzinfo=timezone.utc),
                as_of_date,
            )
            successful = [item for item in candidates if item.status.value == "succeeded"]
            snapshot = max(successful, key=lambda item: item.snapshot_date) if successful else None
        if (
            snapshot is None
            or snapshot.storage_reference is None
            or (merchant_id is not None and snapshot.merchant_id != merchant_id)
        ):
            raise BackupSnapshotNotFoundException("No successful snapshot is available.")

        payload = self._storage.retrieve(snapshot.storage_reference)
        json_export = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["record_type", "record"])
        for collection_name, rows in payload.items():
            for row in rows:
                writer.writerow([collection_name, json.dumps(row, ensure_ascii=False, sort_keys=True)])
        export_reference = self._storage.store(
            {"json": json_export, "csv": csv_buffer.getvalue()}
        )
        now = self._clock.now_utc()
        expires_at = now + timedelta(minutes=self._export_ttl_minutes)
        export_job_id = uuid4()
        download_url = self._storage.generate_signed_url(
            export_reference, self._export_ttl_minutes
        )
        with self._unit_of_work:
            self._backups.save_export(
                {
                    "id": export_job_id,
                    "merchant_id": snapshot.merchant_id,
                    "platform_connection_id": platform_connection_id,
                    "status": "ready",
                    "storage_reference": export_reference,
                    "download_url": download_url,
                    "expires_at": expires_at,
                }
            )
        return {"export_job_id": export_job_id, "status": "processing"}
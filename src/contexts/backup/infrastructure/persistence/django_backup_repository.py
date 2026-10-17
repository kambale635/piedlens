from uuid import UUID

from ...domain.entities.backup_snapshot import BackupSnapshot
from ...domain.value_objects.snapshot_status import SnapshotStatus
from .models import BackupExportRecord, BackupSnapshotRecord


class DjangoBackupRepository:
    """Persist immutable snapshot records and merchant-scoped export jobs."""

    def save_snapshot(self, snapshot: BackupSnapshot) -> None:
        """Insert a snapshot once; succeeded rows are never updated (INV-BK-01)."""
        BackupSnapshotRecord.objects.create(
            id=snapshot.id,
            merchant_id=snapshot.merchant_id,
            platform_connection_id=snapshot.platform_connection_id,
            snapshot_date=snapshot.snapshot_date,
            status=snapshot.status.value,
            data_integrity_hash=snapshot.data_integrity_hash,
            storage_reference=snapshot.storage_reference,
            message_count=snapshot.message_count,
            media_count=snapshot.media_count,
        )

    def find_latest_successful(self, connection_id: UUID) -> BackupSnapshot | None:
        """Find the newest fully successful snapshot for incremental reads/restores."""
        record = BackupSnapshotRecord.objects.filter(
            platform_connection_id=connection_id,
            status=SnapshotStatus.SUCCEEDED.value,
        ).order_by("-snapshot_date", "-id").first()
        return self._to_domain(record) if record else None

    def find_by_date_range(self, connection_id, from_date, to_date) -> list[BackupSnapshot]:
        """Return snapshots in a bounded time range, newest first."""
        records = BackupSnapshotRecord.objects.filter(
            platform_connection_id=connection_id,
            snapshot_date__gte=from_date,
            snapshot_date__lte=to_date,
        ).order_by("-snapshot_date", "-id")
        return [self._to_domain(record) for record in records]

    def list_snapshots(self, merchant_id, connection_id, offset, limit):
        """Return one merchant-scoped page and total count."""
        records = BackupSnapshotRecord.objects.filter(merchant_id=merchant_id)
        if connection_id is not None:
            records = records.filter(platform_connection_id=connection_id)
        total_count = records.count()
        page = records.order_by("-snapshot_date", "-id")[offset : offset + limit]
        return [self._to_domain(record) for record in page], total_count

    def delete_for_merchant(self, merchant_id: UUID) -> list[str]:
        """Remove only this merchant's snapshot/export rows and return owned object refs."""
        references = list(
            BackupSnapshotRecord.objects.filter(merchant_id=merchant_id)
            .exclude(storage_reference__isnull=True)
            .values_list("storage_reference", flat=True)
        )
        references.extend(
            BackupExportRecord.objects.filter(merchant_id=merchant_id).values_list(
                "storage_reference", flat=True
            )
        )
        BackupSnapshotRecord.objects.filter(merchant_id=merchant_id).delete()
        BackupExportRecord.objects.filter(merchant_id=merchant_id).delete()
        return references

    def save_export(self, export: dict) -> None:
        """Insert a ready export job with merchant ownership metadata."""
        BackupExportRecord.objects.create(
            id=export["id"],
            merchant_id=export["merchant_id"],
            platform_connection_id=export["platform_connection_id"],
            status=export["status"],
            storage_reference=export["storage_reference"],
            download_url=export["download_url"],
            expires_at=export["expires_at"],
        )

    def find_export(self, merchant_id: UUID, export_job_id: UUID) -> dict | None:
        """Load an export only when the requesting merchant owns it."""
        record = BackupExportRecord.objects.filter(
            id=export_job_id, merchant_id=merchant_id
        ).first()
        if record is None:
            return None
        return {
            "status": record.status,
            "download_url": record.download_url,
            "expires_at": record.expires_at,
        }

    @staticmethod
    def _to_domain(record: BackupSnapshotRecord) -> BackupSnapshot:
        """Map a database row to the immutable snapshot value."""
        return BackupSnapshot(
            id=record.id,
            merchant_id=record.merchant_id,
            platform_connection_id=record.platform_connection_id,
            snapshot_date=record.snapshot_date,
            status=SnapshotStatus(record.status),
            data_integrity_hash=record.data_integrity_hash,
            storage_reference=record.storage_reference,
            message_count=record.message_count,
            media_count=record.media_count,
        )
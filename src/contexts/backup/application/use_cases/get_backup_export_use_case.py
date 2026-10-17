from uuid import UUID

from ..exceptions import BackupSnapshotNotFoundException
from ..ports.backup_ports import IBackupRepository


class GetBackupExportUseCase:
    """Read export processing state for the merchant that owns the job.

    Contract: docs/15-use-cases-catalog.md#contexte-backup.
    """

    def __init__(self, backups: IBackupRepository) -> None:
        """Receive the Backup persistence port."""
        self._backups = backups

    def execute(self, merchant_id: UUID, export_job_id: UUID) -> dict:
        """Return status and an expiring URL only to the owning merchant."""
        export = self._backups.find_export(merchant_id, export_job_id)
        if export is None:
            raise BackupSnapshotNotFoundException("Backup export was not found.")
        result = {"status": export["status"]}
        if export.get("download_url"):
            result["download_url"] = export["download_url"]
            result["expires_at"] = export["expires_at"]
        return result
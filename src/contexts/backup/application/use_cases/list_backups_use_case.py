from uuid import UUID

from ..ports.backup_ports import IBackupRepository


class ListBackupsUseCase:
    """List one merchant's paginated snapshots, optionally narrowed to a connection.

    Contract: docs/15-use-cases-catalog.md#contexte-backup.
    The merchant ID is supplied from TenantIsolationMiddleware, never from request data.
    """

    def __init__(self, backups: IBackupRepository) -> None:
        """Receive the Backup repository through its application port."""
        self._backups = backups

    def execute(
        self,
        merchant_id: UUID,
        platform_connection_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Return one validated page and the merchant-scoped total count."""
        if page < 1 or page_size < 1 or page_size > 100:
            from shared_kernel.application_exceptions import ValidationException

            raise ValidationException("Page values are outside the supported range.")
        snapshots, total_count = self._backups.list_snapshots(
            merchant_id,
            platform_connection_id,
            (page - 1) * page_size,
            page_size,
        )
        return {"snapshots": snapshots, "total_count": total_count}
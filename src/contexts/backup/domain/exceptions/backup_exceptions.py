from shared_kernel.domain_exceptions import DomainException


class BackupSnapshotImmutableException(DomainException):
    """Reject mutation of a succeeded BackupSnapshot (INV-BK-01)."""

    error_code = "BACKUP_SNAPSHOT_IMMUTABLE"
from enum import StrEnum


class SnapshotStatus(StrEnum):
    """Terminal states for an immutable BackupSnapshot aggregate."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
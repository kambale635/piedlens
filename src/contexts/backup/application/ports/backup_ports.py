from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...domain.entities.backup_snapshot import BackupSnapshot


class IBackupRepository(Protocol):
    """Persistence port for immutable snapshots and export jobs."""

    def save_snapshot(self, snapshot: BackupSnapshot) -> None: ...
    def find_latest_successful(self, connection_id: UUID) -> BackupSnapshot | None: ...
    def find_by_date_range(
        self, connection_id: UUID, from_date: datetime, to_date: datetime
    ) -> list[BackupSnapshot]: ...
    def list_snapshots(
        self, merchant_id: UUID, connection_id: UUID | None, offset: int, limit: int
    ) -> tuple[list[BackupSnapshot], int]: ...
    def delete_for_merchant(self, merchant_id: UUID) -> list[str]: ...
    def save_export(self, export: dict) -> None: ...
    def find_export(self, merchant_id: UUID, export_job_id: UUID) -> dict | None: ...


class IObjectStorage(Protocol):
    """Store snapshot/export payloads and produce expiring signed retrieval URLs."""

    def store(self, file: object) -> str: ...
    def retrieve(self, reference: str) -> object: ...
    def generate_signed_url(self, reference: str, expires_in_minutes: int) -> str: ...
    def delete(self, reference: str) -> None: ...


class IConfirmationTokenVerifier(Protocol):
    """Verify a merchant-bound second confirmation for irreversible deletion (INV-BK-04)."""

    def is_valid(self, merchant_id: UUID, confirmation_token: str) -> bool: ...
    def consume(self, merchant_id: UUID, confirmation_token: str) -> bool: ...


class IDeletionTokenStore(Protocol):
    """Persist only hashes of short-lived single-use deletion tokens (INV-BK-05)."""

    def save(self, merchant_id: UUID, user_id: UUID, token_hash: str, expires_at: datetime) -> None: ...


class IReauthenticationVerifier(Protocol):
    """Verify the current authenticated user's password without exposing Identity storage."""

    def verify(self, user_id: UUID, password: str) -> bool: ...


class IBackupUnitOfWork(Protocol):
    """Transaction boundary for one Backup write and its Outbox row (INV-TR-02)."""

    def __enter__(self) -> "IBackupUnitOfWork": ...
    def __exit__(self, exception_type, exception, traceback) -> bool | None: ...


class IBackupOutbox(Protocol):
    """Backup context event Outbox port (INV-TR-02)."""

    def add(self, event: object) -> None: ...


class IBackupClock(Protocol):
    """Time source for snapshot, export expiry, and deletion events."""

    def now_utc(self) -> datetime: ...
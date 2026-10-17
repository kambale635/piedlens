from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..value_objects.connection_status import ConnectionStatus
from ..value_objects.encrypted_token import EncryptedToken
from ..value_objects.platform_type import PlatformType


@dataclass
class PlatformConnection:
    """Platform connection aggregate holding only an opaque credential (INV-PC-01)."""

    id: UUID
    merchant_id: UUID
    platform_type: PlatformType
    external_account_id: str
    encrypted_access_token: EncryptedToken
    status: ConnectionStatus
    consent_given_at: datetime | None
    last_synced_at: datetime | None = None

    def mark_synced(self, synced_at: datetime) -> None:
        """Record the last successful sync without exposing or changing credentials."""
        if self.status is ConnectionStatus.ACTIVE:
            self.last_synced_at = synced_at
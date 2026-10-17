from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..ports.platform_ports import IPlatformConnectionRepository
from .sync_messages_use_case import SyncMessagesResult, SyncMessagesUseCase


@dataclass(frozen=True)
class SyncActiveConnectionsResult:
    """Per-connection results from a merchant sync job (INV-PC-04)."""

    results: tuple[tuple[UUID, SyncMessagesResult], ...]


class SyncActiveConnectionsJob:
    """Run independent sync transactions and continue after each connection failure (INV-PC-04)."""

    def __init__(
        self,
        connections: IPlatformConnectionRepository,
        sync_use_case: SyncMessagesUseCase,
    ) -> None:
        """Receive the connector-owned listing port and one-connection operation."""
        self._connections = connections
        self._sync_use_case = sync_use_case

    def execute(self, merchant_id: UUID, since: datetime) -> SyncActiveConnectionsResult:
        """Attempt all active connections independently so failures do not cascade."""
        results = []
        for connection in self._connections.find_active_by_merchant(merchant_id):
            try:
                result = self._sync_use_case.execute(connection.id, since)
            except Exception:
                result = SyncMessagesResult(0, connection.last_synced_at, "failed")
            results.append((connection.id, result))
        return SyncActiveConnectionsResult(tuple(results))
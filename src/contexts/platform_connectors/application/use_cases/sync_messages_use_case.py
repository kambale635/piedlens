from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..exceptions import PlatformConnectionNotFoundException
from ..ports.platform_ports import (
    IPlatformClock,
    IPlatformConnectorsOutbox,
    IPlatformConnectorsUnitOfWork,
    IPlatformConnectionRepository,
    IMessageRepository,
)
from ..ports.channel_capabilities import IMessageRetriever
from ..ports.channel_provider_registry import IChannelProviderRegistry
from ...domain.entities.platform_connection import PlatformConnection
from ...domain.events.platform_events import MessageReceived


@dataclass(frozen=True)
class SyncMessagesResult:
    """Result of an isolated synchronization attempt for one platform connection."""

    new_messages_count: int
    last_synced_at: datetime | None
    status: str


class SyncMessagesUseCase:
    """Synchronize one connection so provider errors cannot abort another connection (INV-PC-04).

    Contract: docs/15-use-cases-catalog.md#contexte-platform-connectors.
    New messages and their MessageReceived events commit together, with duplicate delivery
    suppressed by the repository's database uniqueness constraint (INV-PC-03, INV-TR-02).
    """

    def __init__(
        self,
        connections: IPlatformConnectionRepository,
        messages: IMessageRepository,
        providers: IChannelProviderRegistry,
        unit_of_work: IPlatformConnectorsUnitOfWork,
        outbox: IPlatformConnectorsOutbox,
        clock: IPlatformClock,
    ) -> None:
        """Receive all persistence, provider, transaction and time dependencies."""
        self._connections = connections
        self._messages = messages
        self._providers = providers
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(self, platform_connection_id: UUID, since: datetime) -> SyncMessagesResult:
        """Persist new messages atomically or return a failure scoped to this connection."""
        connection = self._connections.find_by_id(platform_connection_id)
        if connection is None:
            raise PlatformConnectionNotFoundException("Platform connection was not found.")
        try:
            retriever = self._providers.require(connection.platform_type.value, IMessageRetriever)
            fetched_messages = retriever.fetch_messages(connection, since)
        except Exception:
            return SyncMessagesResult(0, connection.last_synced_at, "failed")

        synced_at = self._clock.now_utc()
        created_count = 0
        with self._unit_of_work:
            for message in fetched_messages:
                if self._messages.save_if_new(message):
                    created_count += 1
                    self._outbox.add(
                        MessageReceived(
                            merchant_id=message.merchant_id,
                            platform_connection_id=message.platform_connection_id,
                            message_id=message.id,
                            external_message_id=message.external_message_id,
                            external_sender_id=message.external_sender_id,
                            display_name=message.display_name,
                            text_content=message.text_content,
                            received_at=message.received_at,
                        )
                    )
            connection.mark_synced(synced_at)
            self._connections.save(connection)
        return SyncMessagesResult(created_count, synced_at, "succeeded")
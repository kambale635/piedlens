from ...domain.events.platform_events import PlatformConnectionExpired
from ...domain.value_objects.connection_status import ConnectionStatus
from ..exceptions import PlatformConnectionNotFoundException
from ..ports.platform_ports import (
    IPlatformClock,
    IPlatformConnectorsOutbox,
    IPlatformConnectorsUnitOfWork,
    IPlatformConnectionRepository,
    ITokenCipher,
)
from ..ports.channel_capabilities import ITokenRefresher
from ..ports.channel_provider_registry import IChannelProviderRegistry


class RefreshTokensUseCase:
    """Refresh an expiring token or mark the owning connection expired on provider failure.

    Contract: docs/15-use-cases-catalog.md#contexte-platform-connectors.
    Plain tokens remain inside infrastructure; only encrypted values cross this boundary
    and are persisted (INV-PC-01).
    """

    def __init__(self, connections, providers: IChannelProviderRegistry, cipher, unit_of_work, outbox, clock) -> None:
        """Receive persistence, provider, encryption, transaction, event and clock ports."""
        self._connections = connections
        self._providers = providers
        self._cipher = cipher
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(self, platform_connection_id):
        """Refresh one connection's credential and emit expiration only after final failure."""
        connection = self._connections.find_by_id(platform_connection_id)
        if connection is None:
            raise PlatformConnectionNotFoundException("Platform connection was not found.")
        try:
            refresher = self._providers.require(connection.platform_type.value, ITokenRefresher)
            token = refresher.refresh_access_token(connection)
        except Exception:
            now = self._clock.now_utc()
            with self._unit_of_work:
                connection.status = ConnectionStatus.EXPIRED
                self._connections.save(connection)
                self._outbox.add(
                    PlatformConnectionExpired(
                        merchant_id=connection.merchant_id,
                        connection_id=connection.id,
                        occurred_at=now,
                    )
                )
            return {"connection_status": "expired"}

        with self._unit_of_work:
            connection.encrypted_access_token = self._cipher.encrypt(token)
            self._connections.save(connection)
        return {"connection_status": connection.status.value}
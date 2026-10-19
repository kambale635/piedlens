from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...domain.entities.message import Message
from ...domain.entities.platform_connection import PlatformConnection
from ...domain.value_objects.encrypted_token import EncryptedToken
from shared_kernel.ports import IConnectionUsageReader


class IPlatformConnectionRepository(Protocol):
    """Persistence port for PlatformConnection aggregates."""

    def find_by_id(self, connection_id: UUID) -> PlatformConnection | None: ...
    def find_active_by_merchant(self, merchant_id: UUID) -> list[PlatformConnection]: ...
    def save(self, connection: PlatformConnection) -> None: ...


class IMessageRepository(Protocol):
    """Idempotent persistence port keyed by connection and external message ID (INV-PC-03)."""

    def save_if_new(self, message: Message) -> bool: ...


class IPlatformGateway(Protocol):
    """Anti-corruption gateway for OAuth, synchronization, and token refresh."""

    def exchange_oauth_code(
        self, platform_type: str, oauth_code: str, external_account_id: str | None
    ) -> tuple[str, str]: ...

    def fetch_messages(
        self, connection: PlatformConnection, since: datetime
    ) -> list[Message]: ...

    def refresh_access_token(self, connection: PlatformConnection) -> str: ...


class ITokenCipher(Protocol):
    """Infrastructure boundary for credential encryption and decryption (INV-PC-01)."""

    def encrypt(self, plaintext: str) -> EncryptedToken: ...
    def decrypt(self, token: EncryptedToken) -> str: ...


class IWebhookSignatureVerifier(Protocol):
    """Verify provider signatures over the exact raw request body (INV-PC-02)."""

    def verify(self, platform_type: str, raw_body: bytes, signature: str) -> bool: ...


class IWebhookPayloadMapper(Protocol):
    """Translate a verified platform payload into normalized context messages."""

    def map_messages(self, connection: PlatformConnection, payload: dict) -> list[Message]: ...


class IPlatformClock(Protocol):
    """Provide UTC instants for deterministic connection and synchronization workflows."""

    def now_utc(self) -> datetime: ...


class IPlatformConnectorsUnitOfWork(Protocol):
    """Atomic transaction boundary for one connector aggregate and its Outbox."""

    def __enter__(self) -> "IPlatformConnectorsUnitOfWork": ...
    def __exit__(self, exception_type, exception, traceback) -> bool | None: ...


class IPlatformConnectorsOutbox(Protocol):
    """Platform Connectors-owned port for transactional domain events (INV-TR-02)."""

    def add(self, event: object) -> None: ...


class IPlatformConnectorsProcessedEventRepository(Protocol):
    def has_processed(self, event_id: UUID, consumer_name: str) -> bool: ...
    def mark_processed(self, event_id: UUID, consumer_name: str) -> bool: ...


class IPlatformConnectorsMerchantPurger(Protocol):
    def purge_merchant_data(self, event_id: UUID, merchant_id: UUID) -> None: ...


__all__ = [
    "IConnectionUsageReader",
    "IMessageRepository",
    "IPlatformClock",
    "IPlatformConnectorsOutbox",
    "IPlatformConnectorsUnitOfWork",
    "IPlatformConnectionRepository",
    "IPlatformGateway",
    "ITokenCipher",
    "IWebhookPayloadMapper",
    "IWebhookSignatureVerifier",
]
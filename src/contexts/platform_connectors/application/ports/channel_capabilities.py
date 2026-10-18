from datetime import datetime
from typing import Protocol

from ...domain.entities.message import Message
from ...domain.entities.platform_connection import PlatformConnection


class IOAuthCodeExchanger(Protocol):
    def exchange_oauth_code(
        self, channel_code: str, oauth_code: str, external_account_id: str | None
    ) -> tuple[str, str]: ...


class IMessageRetriever(Protocol):
    def fetch_messages(self, connection: PlatformConnection, since: datetime) -> list[Message]: ...


class IMessageSender(Protocol):
    def send_message(
        self, connection: PlatformConnection, recipient_id: str, content: str, idempotency_key: str
    ) -> dict: ...


class IMediaFetcher(Protocol):
    def download_media(self, connection: PlatformConnection, media_id: str) -> bytes: ...


class IChannelHealthChecker(Protocol):
    def check_connection(self, connection: PlatformConnection) -> tuple[str, list[str]]: ...


class IWebhookSignatureVerifier(Protocol):
    def verify(self, channel_code: str, raw_body: bytes, signature: str) -> bool: ...


class ITokenRefresher(Protocol):
    def refresh_access_token(self, connection: PlatformConnection) -> str: ...


class IWebhookMessageNormalizer(Protocol):
    def normalize(self, connection: PlatformConnection, payload: dict) -> list[Message]: ...
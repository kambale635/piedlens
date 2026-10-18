from datetime import datetime

from ...domain.entities.platform_connection import PlatformConnection


class MockOAuthCodeExchanger:
    """Return deterministic non-production credentials for local provider flows."""

    def exchange_oauth_code(self, channel_code, oauth_code, external_account_id):
        if not oauth_code or oauth_code.startswith("invalid"):
            from ...application.exceptions import InvalidOAuthCodeException

            raise InvalidOAuthCodeException("OAuth code could not be exchanged.")
        return f"mock-token-{oauth_code}", external_account_id or f"mock-{channel_code}-{oauth_code}"


class MockMessageRetriever:
    """Represent an empty local inbox without making network requests."""

    def fetch_messages(self, connection: PlatformConnection, since: datetime):
        return []


class MockTokenRefresher:
    """Return a deterministic mock token for provider refresh flows."""

    def refresh_access_token(self, connection: PlatformConnection) -> str:
        return f"refreshed-{connection.id}"


class MockMessageSender:
    """Report a deterministic mock delivery without contacting a platform."""

    def send_message(self, connection, recipient_id, content, idempotency_key):
        return {"status": "sent", "providerMessageId": f"mock-{idempotency_key}"}


class MockMediaFetcher:
    """Return an empty mock payload; real media download requires a provider adapter."""

    def download_media(self, connection, media_id: str) -> bytes:
        return b""


class MockChannelHealthChecker:
    """Report configured mock channels as healthy without external calls."""

    def check_connection(self, connection):
        return "healthy", []
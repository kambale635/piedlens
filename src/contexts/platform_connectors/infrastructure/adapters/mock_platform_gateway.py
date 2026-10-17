from datetime import datetime

from ...application.exceptions import InvalidOAuthCodeException


class MockPlatformGateway:
    """Deterministic connector adapter for local development before provider SDKs exist."""

    def exchange_oauth_code(
        self,
        platform_type: str,
        oauth_code: str,
        external_account_id: str | None = None,
    ) -> tuple[str, str]:
        """Exchange a non-empty mock code for a non-production token and account ID."""
        if not oauth_code or oauth_code.startswith("invalid"):
            raise InvalidOAuthCodeException("OAuth code could not be exchanged.")
        account_id = external_account_id or f"mock-{platform_type}-{oauth_code}"
        return f"mock-token-{oauth_code}", account_id

    def fetch_messages(self, connection, since: datetime) -> list:
        """Return no new messages until a real provider adapter is configured."""
        return []

    def refresh_access_token(self, connection) -> str:
        """Return a deterministic mock replacement token."""
        return f"refreshed-{connection.id}"
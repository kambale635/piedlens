from typing import Protocol
from uuid import UUID


class IConnectionUsageReader(Protocol):
    """Read the active platform-connection usage owned by Platform Connectors."""

    def count_active_connections(self, merchant_id: UUID) -> int:
        """Return the current number of active connections for one merchant."""


class IConnectionPlanReader(Protocol):
    """Read the configured connection capacity owned by Identity."""

    def active_connection_limit(self, merchant_id: UUID) -> int | None:
        """Return the plan's active connection limit, or None for unlimited."""

class IMerchantCountryReader(Protocol):
    """Read a merchant's configured country without importing Identity into consumers."""

    def country_code_for(self, merchant_id: UUID) -> str | None:
        """Return the ISO country code configured for the merchant, if found."""


class IConnectionConsentReader(Protocol):
    """Read Platform Connectors consent metadata for Backup without cross-context imports."""

    def consent_for(self, connection_id: UUID) -> tuple[UUID, object | None] | None:
        """Return merchant ID and consent timestamp for a platform connection."""


class IBackupMessageReader(Protocol):
    """Read normalized message deltas from the owning Platform Connectors context."""

    def read_messages(self, connection_id: UUID, since: object | None) -> list[dict]:
        """Return serializable message records after the prior snapshot timestamp."""


class IBackupContactReader(Protocol):
    """Read contact deltas from the owning CRM context."""

    def read_contacts(
        self, merchant_id: UUID, connection_id: UUID, since: object | None
    ) -> list[dict]:
        """Return serializable contact records after the prior snapshot timestamp."""


class IAccountHealthChecker(Protocol):
    """Check connection health through Platform Connectors capabilities."""

    def check_account_status(self, connection_id: UUID) -> tuple[str, list[str]]:
        """Return a stable health state and configured provider signals."""
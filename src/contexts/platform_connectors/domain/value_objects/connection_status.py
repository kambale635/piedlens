from enum import StrEnum


class ConnectionStatus(StrEnum):
    """Lifecycle states persisted for a merchant's platform connection."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
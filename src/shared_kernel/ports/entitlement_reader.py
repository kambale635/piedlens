from typing import Protocol
from uuid import UUID


class IEntitlementReader(Protocol):
    """Read a merchant's effective plan limits without exposing billing storage."""

    def entitlements_for(self, merchant_id: UUID) -> dict[str, object]:
        """Return configured entitlement values for the merchant's active plan."""

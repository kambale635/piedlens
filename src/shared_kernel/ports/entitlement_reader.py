from typing import Protocol
from uuid import UUID


class IEntitlementReader(Protocol):
    """Read a merchant's effective plan limits without exposing billing storage."""

    def entitlements_for(self, merchant_id: UUID) -> dict[str, object]:
        """Return configured entitlement values for the merchant's active plan."""

    def entitlements_for_plan(self, plan_code: str) -> dict[str, object]:
        """Return configured entitlement values for one active plan code."""

from typing import Protocol


class IPlanCatalogReader(Protocol):
    """Validate plan codes against the active Billing catalog."""

    def is_active_plan(self, plan_code: str) -> bool:
        """Return whether the given plan code is configured and active."""

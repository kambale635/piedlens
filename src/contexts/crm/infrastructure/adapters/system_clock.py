"""Module: contexts/crm/infrastructure/system_clock.py
Context: CRM.
Role: provide the UTC clock adapter for scheduled CRM application services.
"""

from datetime import datetime, timezone


class SystemCRMClock:
    """Return timezone-aware UTC time to CRM scheduled application services."""

    def now_utc(self) -> datetime:
        """Read the current instant from the system clock in UTC."""
        return datetime.now(timezone.utc)
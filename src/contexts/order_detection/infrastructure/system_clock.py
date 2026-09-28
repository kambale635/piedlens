"""Module: contexts/order_detection/infrastructure/system_clock.py
Context: Order Detection.
Role: provide the current timezone-aware system time through the application clock port.
"""

from datetime import datetime, timezone


class SystemClock:
    """Provide UTC timestamps to application operations."""

    def now(self) -> datetime:
        """Return the current UTC instant."""
        return datetime.now(timezone.utc)
from datetime import datetime, timezone


class SystemPlatformClock:
    """Supply aware UTC timestamps to Platform Connectors application services."""

    def now_utc(self) -> datetime:
        """Return the current UTC instant for persistence and events."""
        return datetime.now(timezone.utc)
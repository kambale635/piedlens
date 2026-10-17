from datetime import datetime, timezone


class SystemBackupClock:
    """Supply aware UTC instants for backup snapshots, exports, and deletion events."""

    def now_utc(self) -> datetime:
        """Return the current UTC timestamp."""
        return datetime.now(timezone.utc)
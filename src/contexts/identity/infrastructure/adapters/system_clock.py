from datetime import datetime, timezone


class SystemIdentityClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)
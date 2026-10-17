from datetime import datetime, timezone


class SystemAccessControlClock:
    def now_utc(self):
        return datetime.now(timezone.utc)
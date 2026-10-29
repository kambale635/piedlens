from datetime import datetime, timezone


class SystemPaymentClock:
    """Provide UTC instants to payment application services (INV-PAY-06/T8)."""

    def now_utc(self):
        return datetime.now(timezone.utc)

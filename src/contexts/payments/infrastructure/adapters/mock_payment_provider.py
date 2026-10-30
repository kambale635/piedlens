import hashlib
import hmac
from datetime import datetime, timezone

from django.conf import settings


class MockPaymentProvider:
    """Deterministic checkout adapter for tests and development (INV-PAY-01/06)."""

    def __init__(self, outcome="pending"):
        if outcome not in {"pending", "succeeded", "failed"}:
            raise ValueError("Mock outcome must be pending, succeeded, or failed.")
        self.outcome = outcome

    def initiate(self, *, attempt_id, amount_minor, currency, idempotency_key):
        """Return deterministic instructions without an external network call."""
        return {
            "provider_reference": f"mock:{attempt_id}",
            "outcome": self.outcome,
            "instructions": {"reference": str(attempt_id), "amountMinor": amount_minor, "currency": currency},
        }

    def verify(self, provider_code, raw_body, signature, timestamp):
        """Verify only the configured local mock HMAC; never a real provider signature."""
        if provider_code != "mock" or not timestamp:
            return False
        try:
            timestamp_seconds = int(timestamp)
        except (TypeError, ValueError):
            return False
        age_seconds = abs(int(datetime.now(timezone.utc).timestamp()) - timestamp_seconds)
        if age_seconds > settings.PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
            return False
        secret = settings.PAYMENT_WEBHOOK_SECRETS.get(provider_code, "")
        expected = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("ascii") + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
        return bool(secret) and hmac.compare_digest(expected, signature.removeprefix("sha256="))

    def status_for(self, provider_reference):
        return {"outcome": self.outcome, "provider_reference": provider_reference}

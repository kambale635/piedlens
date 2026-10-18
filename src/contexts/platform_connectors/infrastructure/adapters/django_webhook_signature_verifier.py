import hashlib
import hmac
import time

from django.conf import settings


class DjangoWebhookSignatureVerifier:
    """Verify HMAC-SHA256 signatures against configured per-platform secrets (INV-PC-02)."""

    def verify(
        self, platform_type: str, raw_body: bytes, signature: str, timestamp: str
    ) -> bool:
        """Validate timestamp tolerance and compare the raw-body HMAC in constant time."""
        secret = settings.PLATFORM_WEBHOOK_SECRETS.get(platform_type)
        if (
            not secret
            or not signature.startswith("sha256=")
            or not timestamp.isascii()
            or not timestamp.isdigit()
        ):
            return False
        timestamp_seconds = int(timestamp)
        if str(timestamp_seconds) != timestamp:
            return False
        tolerance = settings.PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS
        if abs(int(time.time()) - timestamp_seconds) > tolerance:
            return False
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"), timestamp.encode("ascii") + b"." + raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
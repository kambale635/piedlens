import hashlib
import hmac

from django.conf import settings


class DjangoWebhookSignatureVerifier:
    """Verify HMAC-SHA256 signatures against configured per-platform secrets (INV-PC-02)."""

    def verify(self, platform_type: str, raw_body: bytes, signature: str) -> bool:
        """Compare signatures in constant time over the exact unparsed request body."""
        secret = settings.PLATFORM_WEBHOOK_SECRETS.get(platform_type)
        if not secret or not signature.startswith("sha256="):
            return False
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
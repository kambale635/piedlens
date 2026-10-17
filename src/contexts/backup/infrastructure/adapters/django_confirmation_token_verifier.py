import hashlib
import hmac
import time

from django.conf import settings


class DjangoConfirmationTokenVerifier:
    """Verify a merchant-bound, short-lived HMAC confirmation token (INV-BK-04)."""

    MAX_AGE_SECONDS = 600

    def is_valid(self, merchant_id, confirmation_token: str) -> bool:
        """Accept only a second-confirmation token signed for this merchant and time window."""
        if not confirmation_token or not settings.BACKUP_DELETE_CONFIRMATION_SECRET:
            return False
        parts = confirmation_token.split(":")
        if len(parts) != 4 or parts[0] != str(merchant_id):
            return False
        _, issued_at, nonce, supplied_signature = parts
        try:
            issued = int(issued_at)
        except ValueError:
            return False
        now = int(time.time())
        if issued > now or now - issued > self.MAX_AGE_SECONDS or not nonce:
            return False
        message = f"{parts[0]}:{issued_at}:{nonce}".encode("utf-8")
        expected = hmac.new(
            settings.BACKUP_DELETE_CONFIRMATION_SECRET.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, supplied_signature)
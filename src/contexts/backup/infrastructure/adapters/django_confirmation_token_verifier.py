import hashlib
import hmac
from datetime import datetime, timezone

from ..persistence.models import MerchantDeletionTokenRecord


class DjangoConfirmationTokenVerifier:
    """Verify a merchant-bound, short-lived HMAC confirmation token (INV-BK-04)."""

    def is_valid(self, merchant_id, confirmation_token: str) -> bool:
        """Check a token without consuming it; deletion must call consume instead."""
        record = self._find_record(merchant_id, confirmation_token)
        return record is not None

    def consume(self, merchant_id, confirmation_token: str) -> bool:
        """Atomically consume a valid, unexpired one-use token inside Backup's transaction."""
        record = self._find_record(merchant_id, confirmation_token)
        if record is None:
            return False
        updated = MerchantDeletionTokenRecord.objects.filter(
            id=record.id,
            consumed_at__isnull=True,
            expires_at__gt=datetime.now(timezone.utc),
        ).update(consumed_at=datetime.now(timezone.utc))
        return updated == 1

    @staticmethod
    def _find_record(merchant_id, confirmation_token):
        if not confirmation_token:
            return None
        token_hash = hashlib.sha256(confirmation_token.encode()).hexdigest()
        record = MerchantDeletionTokenRecord.objects.filter(
            merchant_id=merchant_id,
            token_hash=token_hash,
            consumed_at__isnull=True,
            expires_at__gt=datetime.now(timezone.utc),
        ).first()
        if record is None:
            return None
        expected = hashlib.sha256(confirmation_token.encode()).hexdigest()
        return record if hmac.compare_digest(record.token_hash, expected) else None
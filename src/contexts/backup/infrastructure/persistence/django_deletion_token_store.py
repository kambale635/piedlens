from ...application.ports.backup_ports import IDeletionTokenStore
from .models import MerchantDeletionTokenRecord


class DjangoDeletionTokenStore(IDeletionTokenStore):
    """Persist deletion confirmation digests without retaining raw bearer tokens."""

    def save(self, merchant_id, user_id, token_hash, expires_at) -> None:
        """Save the token digest and ownership metadata; the caller owns no token log."""
        MerchantDeletionTokenRecord.objects.create(
            merchant_id=merchant_id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
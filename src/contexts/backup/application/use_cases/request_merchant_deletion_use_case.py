import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

from ..exceptions import InvalidReauthenticationException
from ..ports.backup_ports import (
    IBackupClock,
    IDeletionTokenStore,
    IReauthenticationVerifier,
)


class RequestMerchantDeletionUseCase:
    """Issue a one-use deletion token after password reauthentication (INV-BK-05).

    Contract: docs/15-use-cases-catalog.md#RequestMerchantDeletionUseCase.
    The raw token is returned once; only its SHA-256 digest is persisted and it
    must never be logged.
    """

    TOKEN_TTL = timedelta(minutes=15)

    def __init__(
        self,
        reauthentication: IReauthenticationVerifier,
        tokens: IDeletionTokenStore,
        clock: IBackupClock,
    ) -> None:
        self._reauthentication = reauthentication
        self._tokens = tokens
        self._clock = clock

    def execute(self, merchant_id: UUID, user_id: UUID, password: str) -> dict:
        """Authenticate the caller and issue a merchant-scoped, hashed confirmation token (INV-BK-05)."""
        if not self._reauthentication.verify(user_id, password):
            raise InvalidReauthenticationException("Password reauthentication failed.")
        token = secrets.token_urlsafe(32)
        expires_at = self._clock.now_utc() + self.TOKEN_TTL
        self._tokens.save(merchant_id, user_id, hashlib.sha256(token.encode()).hexdigest(), expires_at)
        return {"confirmation_token": token, "expires_at": expires_at}
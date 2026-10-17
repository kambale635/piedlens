from datetime import datetime, timedelta, timezone
from uuid import UUID

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing


class DjangoPasswordHasher:
    def hash(self, password: str) -> str:
        return make_password(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return check_password(password, password_hash)


class DjangoTokenService:
    salt = "piedlens.identity.tokens"

    def __init__(self, now=None) -> None:
        self.now = now or (lambda: datetime.now(timezone.utc))

    def issue_tokens(self, user_id: UUID) -> dict:
        access = self.issue_access_token(user_id)
        refresh = signing.dumps(
            {"sub": str(user_id), "type": "refresh"}, salt=self.salt, compress=True
        )
        return {
            "accessToken": access["accessToken"],
            "refreshToken": refresh,
            "expiresAt": access["expiresAt"],
        }

    def issue_access_token(self, user_id: UUID) -> dict:
        expires_at = self.now() + timedelta(seconds=settings.IDENTITY_ACCESS_TOKEN_TTL_SECONDS)
        token = signing.dumps(
            {"sub": str(user_id), "type": "access"}, salt=self.salt, compress=True
        )
        return {"accessToken": token, "expiresAt": expires_at}

    def refresh_access_token(self, refresh_token: str) -> dict:
        payload = signing.loads(
            refresh_token,
            salt=self.salt,
            max_age=settings.IDENTITY_REFRESH_TOKEN_TTL_SECONDS,
        )
        if payload.get("type") != "refresh":
            raise signing.BadSignature("Not a refresh token")
        user_id = UUID(payload["sub"])
        return {**self.issue_access_token(user_id), "userId": user_id}

    def decode_access_token(self, token: str) -> UUID:
        payload = signing.loads(
            token,
            salt=self.salt,
            max_age=settings.IDENTITY_ACCESS_TOKEN_TTL_SECONDS,
        )
        if payload.get("type") != "access":
            raise signing.BadSignature("Not an access token")
        return UUID(payload["sub"])
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache

from ..persistence.models import AuthSessionRecord, UserRecord


class DjangoPasswordHasher:
    def hash(self, password: str) -> str:
        return make_password(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return check_password(password, password_hash)

    def validate(self, password: str) -> bool:
        try:
            validate_password(password)
        except ValidationError:
            return False
        return True


class DjangoLoginBackoff:
    """Apply progressive cache-backed delays to a source-IP/phone attempt key."""

    def __init__(self, cache_backend=None) -> None:
        self._cache = cache_backend or cache
        self._base_seconds = settings.IDENTITY_LOGIN_BACKOFF_BASE_SECONDS
        self._max_seconds = settings.IDENTITY_LOGIN_BACKOFF_MAX_SECONDS
        self._window_seconds = settings.IDENTITY_LOGIN_BACKOFF_WINDOW_SECONDS

    def is_blocked(self, attempt_key: str) -> bool:
        return bool(self._cache.get(self._cache_key("blocked", attempt_key)))

    def record_failure(self, attempt_key: str) -> None:
        failure_key = self._cache_key("failures", attempt_key)
        self._cache.add(failure_key, 0, timeout=self._window_seconds)
        try:
            failures = self._cache.incr(failure_key)
        except ValueError:
            self._cache.set(failure_key, 1, timeout=self._window_seconds)
            failures = 1
        exponent = min(failures - 1, 20)
        delay_seconds = min(self._base_seconds * (2 ** exponent), self._max_seconds)
        self._cache.set(
            self._cache_key("blocked", attempt_key), True, timeout=delay_seconds
        )

    def clear(self, attempt_key: str) -> None:
        self._cache.delete_many(
            [self._cache_key("blocked", attempt_key), self._cache_key("failures", attempt_key)]
        )

    @staticmethod
    def _cache_key(kind: str, attempt_key: str) -> str:
        digest = hashlib.sha256(attempt_key.encode("utf-8")).hexdigest()
        return f"identity:login:{kind}:{digest}"


class DjangoTokenService:
    salt = "piedlens.identity.tokens"

    def __init__(self, now=None) -> None:
        self.now = now or (lambda: datetime.now(timezone.utc))

    def issue_tokens(self, user_id: UUID) -> dict:
        now = self.now()
        session_id = uuid4()
        family_id = uuid4()
        refresh, expires_at = self._issue_refresh_token(user_id, session_id, family_id, now)
        with transaction.atomic():
            AuthSessionRecord.objects.create(
                id=session_id,
                user_id=user_id,
                family_id=family_id,
                refresh_token_hash=self._token_hash(refresh),
                created_at=now,
                expires_at=expires_at,
            )
            access = self._issue_access_token(user_id, session_id, now)
        return {
            "accessToken": access["accessToken"],
            "refreshToken": refresh,
            "expiresAt": access["expiresAt"],
        }

    def _issue_access_token(self, user_id: UUID, session_id: UUID, now: datetime) -> dict:
        expires_at = now + timedelta(seconds=settings.IDENTITY_ACCESS_TOKEN_TTL_SECONDS)
        token = signing.dumps(
            {"sub": str(user_id), "sid": str(session_id), "type": "access"},
            salt=self.salt,
            compress=True,
        )
        return {"accessToken": token, "expiresAt": expires_at}

    def _issue_refresh_token(
        self, user_id: UUID, session_id: UUID, family_id: UUID, now: datetime
    ) -> tuple[str, datetime]:
        expires_at = now + timedelta(seconds=settings.IDENTITY_REFRESH_TOKEN_TTL_SECONDS)
        token = signing.dumps(
            {
                "sub": str(user_id),
                "sid": str(session_id),
                "family": str(family_id),
                "type": "refresh",
            },
            salt=self.salt,
            compress=True,
        )
        return token, expires_at

    def refresh_access_token(self, refresh_token: str) -> dict:
        payload = signing.loads(
            refresh_token,
            salt=self.salt,
            max_age=settings.IDENTITY_REFRESH_TOKEN_TTL_SECONDS,
        )
        if payload.get("type") != "refresh":
            raise signing.BadSignature("Not a refresh token")
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
        family_id = UUID(payload["family"])
        now = self.now()
        token_hash = self._token_hash(refresh_token)
        invalid = False
        issued = None
        with transaction.atomic():
            session = AuthSessionRecord.objects.select_for_update().filter(
                id=session_id,
                family_id=family_id,
                user_id=user_id,
            ).first()
            if session is None:
                invalid = True
            elif not hmac.compare_digest(session.refresh_token_hash, token_hash):
                AuthSessionRecord.objects.filter(
                    family_id=session.family_id,
                    revoked_at__isnull=True,
                ).update(revoked_at=now)
                invalid = True
            elif session.revoked_at is not None:
                if session.replaced_by_session_id is not None:
                    AuthSessionRecord.objects.filter(
                        family_id=session.family_id,
                        revoked_at__isnull=True,
                    ).update(revoked_at=now)
                invalid = True
            elif session.expires_at <= now:
                session.revoked_at = now
                session.save(update_fields=["revoked_at"])
                invalid = True
            elif not UserRecord.objects.filter(id=user_id, status="active").exists():
                AuthSessionRecord.objects.filter(
                    family_id=session.family_id,
                    revoked_at__isnull=True,
                ).update(revoked_at=now)
                invalid = True
            else:
                replacement_id = uuid4()
                replacement, expires_at = self._issue_refresh_token(
                    user_id, replacement_id, session.family_id, now
                )
                AuthSessionRecord.objects.create(
                    id=replacement_id,
                    user_id=user_id,
                    family_id=session.family_id,
                    refresh_token_hash=self._token_hash(replacement),
                    created_at=now,
                    expires_at=expires_at,
                )
                session.revoked_at = now
                session.replaced_by_session_id = replacement_id
                session.save(update_fields=["revoked_at", "replaced_by_session_id"])
                issued = {
                    **self._issue_access_token(user_id, replacement_id, now),
                    "refreshToken": replacement,
                    "userId": user_id,
                }
        if invalid:
            raise signing.BadSignature("Refresh token is invalid or has already been used.")
        return issued

    def revoke_refresh_token(self, refresh_token: str) -> None:
        try:
            payload = signing.loads(
                refresh_token,
                salt=self.salt,
                max_age=settings.IDENTITY_REFRESH_TOKEN_TTL_SECONDS,
            )
            if payload.get("type") != "refresh":
                return
            session_id = UUID(payload["sid"])
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            return
        token_hash = self._token_hash(refresh_token)
        with transaction.atomic():
            session = AuthSessionRecord.objects.select_for_update().filter(id=session_id).first()
            if session is not None and hmac.compare_digest(session.refresh_token_hash, token_hash):
                if session.revoked_at is None:
                    session.revoked_at = self.now()
                    session.save(update_fields=["revoked_at"])

    def revoke_all_sessions(self, user_id: UUID) -> int:
        return AuthSessionRecord.objects.filter(
            user_id=user_id,
            revoked_at__isnull=True,
        ).update(revoked_at=self.now())

    def decode_access_token(self, token: str) -> UUID:
        payload = signing.loads(
            token,
            salt=self.salt,
            max_age=settings.IDENTITY_ACCESS_TOKEN_TTL_SECONDS,
        )
        if payload.get("type") != "access":
            raise signing.BadSignature("Not an access token")
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
        if not AuthSessionRecord.objects.filter(
            id=session_id,
            user_id=user_id,
            revoked_at__isnull=True,
            expires_at__gt=self.now(),
        ).exists():
            raise signing.BadSignature("Access token session has been revoked.")
        return user_id

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
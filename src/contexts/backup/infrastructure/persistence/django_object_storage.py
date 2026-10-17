import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

from ...application.exceptions import BackupSnapshotNotFoundException
from .models import BackupObjectRecord


class DjangoObjectStorage:
    """Local database-backed object-store adapter with HMAC-expiring URLs for development."""

    def store(self, file: object) -> str:
        """Store a JSON-compatible object and return its opaque storage reference."""
        record = BackupObjectRecord.objects.create(payload=json.loads(DjangoJSONEncoder().encode(file)))
        return str(record.id)

    def retrieve(self, reference: str) -> object:
        """Load one stored payload by its opaque reference."""
        record = BackupObjectRecord.objects.filter(id=reference).first()
        if record is None:
            raise BackupSnapshotNotFoundException("Stored backup object was not found.")
        return record.payload

    def generate_signed_url(self, reference: str, expires_in_minutes: int) -> str:
        """Create an expiring URL signature without exposing storage credentials."""
        secret = settings.BACKUP_EXPORT_SIGNING_SECRET
        if not secret:
            raise ValueError("BACKUP_EXPORT_SIGNING_SECRET is required.")
        expires = int((datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)).timestamp())
        message = f"{reference}:{expires}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return f"{settings.BACKUP_EXPORT_BASE_URL.rstrip('/')}/{reference}?expires={expires}&signature={signature}"

    def verify_signed_url(self, reference: str, expires: str, signature: str) -> bool:
        """Verify an unexpired HMAC bearer URL before returning stored data."""
        secret = settings.BACKUP_EXPORT_SIGNING_SECRET
        try:
            expires_at = int(expires)
        except (TypeError, ValueError):
            return False
        if not secret or expires_at < int(datetime.now(timezone.utc).timestamp()):
            return False
        message = f"{reference}:{expires_at}".encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def delete(self, reference: str) -> None:
        """Delete one object from the local development store."""
        try:
            BackupObjectRecord.objects.filter(id=UUID(reference)).delete()
        except ValueError:
            return
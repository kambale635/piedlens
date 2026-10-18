import base64
import json
import os
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder


class DjangoBackupPayloadCipher:
    """Encrypt backup snapshots and export payloads with versioned AES-256-GCM (INV-BK-01)."""

    NONCE_BYTES = 12
    ENVELOPE_KEY = "_piedlens_encrypted_backup"

    def __init__(self) -> None:
        self._active_version = settings.BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION
        if re.fullmatch(r"v[1-9][0-9]*", self._active_version) is None:
            raise ValueError("Backup encryption version must be vN.")
        self._ciphers = {
            version: AESGCM(self._decode_key(version, encoded_key))
            for version, encoded_key in settings.BACKUP_DATA_ENCRYPTION_KEYS.items()
        }
        if self._active_version not in self._ciphers:
            raise ValueError("The active backup data encryption key is not configured.")

    @staticmethod
    def _decode_key(version: str, encoded_key: str) -> bytes:
        try:
            key = base64.b64decode(encoded_key.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError(f"Backup data key {version} must be URL-safe base64.") from error
        if len(key) != 32:
            raise ValueError(f"Backup data key {version} must decode to 32 bytes.")
        return key

    def encrypt(self, payload: object) -> dict[str, str]:
        """Serialize and encrypt a payload into a versioned JSON-compatible envelope."""
        nonce = os.urandom(self.NONCE_BYTES)
        plaintext = json.dumps(
            payload, cls=DjangoJSONEncoder, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        associated_data = self._active_version.encode("ascii")
        ciphertext = self._ciphers[self._active_version].encrypt(
            nonce, plaintext, associated_data
        )
        return {
            self.ENVELOPE_KEY: self._active_version,
            "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        }

    def decrypt(self, payload: object) -> object:
        """Decrypt a versioned payload; pass historical plaintext objects through for migration."""
        if not isinstance(payload, dict) or self.ENVELOPE_KEY not in payload:
            return payload
        version = payload[self.ENVELOPE_KEY]
        cipher = self._ciphers.get(version)
        if cipher is None:
            raise ValueError(f"Backup data key {version} is not configured.")
        nonce = base64.urlsafe_b64decode(payload["nonce"].encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(payload["ciphertext"].encode("ascii"))
        plaintext = cipher.decrypt(nonce, ciphertext, version.encode("ascii"))
        return json.loads(plaintext.decode("utf-8"))

    def key_version(self, payload: object) -> str | None:
        """Return an envelope's key version or None for a legacy plaintext payload."""
        if isinstance(payload, dict):
            return payload.get(self.ENVELOPE_KEY)
        return None

    @property
    def active_version(self) -> str:
        """Expose the active key version without exposing key material."""
        return self._active_version
import base64
import os
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


class DjangoCampaignContentCipher:
    """Encrypt persisted CRM campaign text with versioned AES-256-GCM (INV-CRM-10)."""

    NONCE_BYTES = 12

    def __init__(self) -> None:
        self._active_version = settings.CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION
        if re.fullmatch(r"v[1-9][0-9]*", self._active_version) is None:
            raise ValueError("CRM message encryption version must be vN.")
        self._ciphers = {
            version: AESGCM(self._decode_key(version, encoded_key))
            for version, encoded_key in settings.CRM_MESSAGE_ENCRYPTION_KEYS.items()
        }
        if self._active_version not in self._ciphers:
            raise ValueError("The active CRM message encryption key is not configured.")

    @staticmethod
    def _decode_key(version: str, encoded_key: str) -> bytes:
        try:
            key = base64.b64decode(encoded_key.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError(f"CRM message key {version} must be URL-safe base64.") from error
        if len(key) != 32:
            raise ValueError(f"CRM message key {version} must decode to 32 bytes.")
        return key

    def encrypt(self, plaintext: str) -> str:
        """Encrypt one campaign template using the active CRM key version."""
        nonce = os.urandom(self.NONCE_BYTES)
        ciphertext = self._ciphers[self._active_version].encrypt(
            nonce, plaintext.encode("utf-8"), self._active_version.encode("ascii")
        )
        value = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{self._active_version}.{value}"

    def decrypt(self, value: str) -> str:
        """Decrypt a stored template or pass legacy plaintext through for migration."""
        if "." not in value:
            return value
        version, encoded = value.split(".", 1)
        cipher = self._ciphers.get(version)
        if cipher is None:
            raise ValueError(f"CRM message key {version} is not configured.")
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        plaintext = cipher.decrypt(
            raw[: self.NONCE_BYTES], raw[self.NONCE_BYTES :], version.encode("ascii")
        )
        return plaintext.decode("utf-8")

    def key_version(self, value: str) -> str | None:
        if "." not in value:
            return None
        version, _ = value.split(".", 1)
        if version not in self._ciphers:
            raise ValueError(f"CRM message key {version} is not configured.")
        return version

    @property
    def active_version(self) -> str:
        return self._active_version
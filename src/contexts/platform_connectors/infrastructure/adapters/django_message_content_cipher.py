import base64
import os
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


class DjangoMessageContentCipher:
    """Encrypt persisted message text with versioned AES-256-GCM (INV-PC-06)."""

    NONCE_BYTES = 12

    def __init__(self) -> None:
        self._active_version = settings.PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION
        if re.fullmatch(r"v[1-9][0-9]*", self._active_version) is None:
            raise ValueError("Platform message encryption version must be vN.")
        self._ciphers = {
            version: AESGCM(self._decode_key(version, encoded_key))
            for version, encoded_key in settings.PLATFORM_MESSAGE_ENCRYPTION_KEYS.items()
        }
        if self._active_version not in self._ciphers:
            raise ValueError("The active platform message encryption key is not configured.")

    @staticmethod
    def _decode_key(version: str, encoded_key: str) -> bytes:
        try:
            key = base64.b64decode(encoded_key.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError(f"Platform message key {version} must be URL-safe base64.") from error
        if len(key) != 32:
            raise ValueError(f"Platform message key {version} must decode to 32 bytes.")
        return key

    def encrypt(self, plaintext: str) -> str:
        """Encrypt message text using the currently active key version."""
        """Encrypt message text and encode its key version with the ciphertext."""
        version = self._active_version
        nonce = os.urandom(self.NONCE_BYTES)
        ciphertext = self._ciphers[version].encrypt(
            nonce, plaintext.encode("utf-8"), version.encode("ascii")
        )
        encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{version}.{encoded}"

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt stored text, accepting historical plaintext during migration."""
        """Decrypt current or retained historical ciphertext; return old plaintext for migration."""
        if "." not in ciphertext:
            return ciphertext
        version, encoded = ciphertext.split(".", 1)
        cipher = self._ciphers.get(version)
        if cipher is None:
            raise ValueError(f"Platform message key {version} is not configured.")
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        plaintext = cipher.decrypt(
            raw[: self.NONCE_BYTES], raw[self.NONCE_BYTES :], version.encode("ascii")
        )
        return plaintext.decode("utf-8")

    def key_version(self, ciphertext: str) -> str | None:
        """Return the key version or None when the value predates application encryption."""
        if "." not in ciphertext:
            return None
        version, _ = ciphertext.split(".", 1)
        if version not in self._ciphers:
            raise ValueError(f"Platform message key {version} is not configured.")
        return version

    @property
    def active_version(self) -> str:
        """Expose the active key version without exposing key material."""
        return self._active_version
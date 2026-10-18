import base64
import os
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from ...domain.value_objects.encrypted_token import EncryptedToken


class DjangoAesTokenCipher:
    """Encrypt versioned platform credentials at rest with AES-256-GCM (INV-PC-01)."""

    NONCE_BYTES = 12

    def __init__(self) -> None:
        """Load the active key and available historical keys from Django settings."""
        self._active_key_version = settings.PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION
        self._ciphers = {
            version: AESGCM(self._decode_key(version, encoded_key))
            for version, encoded_key in settings.PLATFORM_TOKEN_ENCRYPTION_KEYS.items()
        }
        if self._active_key_version not in self._ciphers:
            raise ValueError("The active platform token encryption key is not configured.")
        if re.fullmatch(r"v[1-9][0-9]*", self._active_key_version) is None:
            raise ValueError("The active platform token encryption version must be vN.")

    @staticmethod
    def _decode_key(version: str, encoded_key: str) -> bytes:
        try:
            key = base64.b64decode(encoded_key.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError(f"Platform token key {version} must be URL-safe base64.") from error
        if len(key) != 32:
            raise ValueError(f"Platform token key {version} must decode to 32 bytes.")
        return key

    @property
    def active_key_version(self) -> str:
        """Expose the configured version without exposing key material."""
        return self._active_key_version

    def encrypt(self, plaintext: str) -> EncryptedToken:
        """Return an authenticated, version-tagged ciphertext value."""
        nonce = os.urandom(self.NONCE_BYTES)
        version = self._active_key_version
        ciphertext = self._ciphers[version].encrypt(
            nonce, plaintext.encode("utf-8"), version.encode("ascii")
        )
        encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return EncryptedToken(f"{version}.{encoded}")

    def key_version(self, token: EncryptedToken) -> str:
        """Return the key version, identifying old untagged ciphertext as legacy."""
        if "." not in token.value:
            return "legacy"
        version, _ = token.value.split(".", 1)
        if version not in self._ciphers or version == "legacy":
            raise ValueError("Platform token references an unavailable key version.")
        return version

    def decrypt(self, token: EncryptedToken) -> str:
        """Decrypt only inside infrastructure for an external provider call."""
        version = self.key_version(token)
        cipher = self._ciphers.get(version)
        if cipher is None:
            raise ValueError("The legacy platform token key is not configured.")
        encoded = token.value.split(".", 1)[1] if version != "legacy" else token.value
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        associated_data = None if version == "legacy" else version.encode("ascii")
        plaintext = cipher.decrypt(
            raw[: self.NONCE_BYTES], raw[self.NONCE_BYTES :], associated_data
        )
        return plaintext.decode("utf-8")
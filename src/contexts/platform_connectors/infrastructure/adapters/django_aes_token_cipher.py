import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from ...domain.value_objects.encrypted_token import EncryptedToken


class DjangoAesTokenCipher:
    """Encrypt platform credentials at rest with AES-256-GCM (INV-PC-01)."""

    NONCE_BYTES = 12

    def __init__(self) -> None:
        """Load the base64-encoded 256-bit key from environment-backed settings."""
        encoded_key = settings.PLATFORM_TOKEN_ENCRYPTION_KEY
        try:
            key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError("PLATFORM_TOKEN_ENCRYPTION_KEY must be URL-safe base64.") from error
        if len(key) != 32:
            raise ValueError("PLATFORM_TOKEN_ENCRYPTION_KEY must decode to 32 bytes.")
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: str) -> EncryptedToken:
        """Return nonce+ciphertext encoded as an opaque token value."""
        nonce = os.urandom(self.NONCE_BYTES)
        ciphertext = self._cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
        return EncryptedToken(base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii"))

    def decrypt(self, token: EncryptedToken) -> str:
        """Decrypt only inside infrastructure for an external provider call."""
        raw = base64.urlsafe_b64decode(token.value.encode("ascii"))
        plaintext = self._cipher.decrypt(raw[: self.NONCE_BYTES], raw[self.NONCE_BYTES :], None)
        return plaintext.decode("utf-8")
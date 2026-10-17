import base64
import hashlib
import hmac
import unittest

from django.test import override_settings

from contexts.platform_connectors.domain.value_objects.encrypted_token import EncryptedToken
from contexts.platform_connectors.infrastructure.adapters.django_aes_token_cipher import (
    DjangoAesTokenCipher,
)
from contexts.platform_connectors.infrastructure.adapters.django_webhook_signature_verifier import (
    DjangoWebhookSignatureVerifier,
)


class PlatformSecurityAdapterTests(unittest.TestCase):
    @override_settings(PLATFORM_TOKEN_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"k" * 32).decode())
    def test_aes_cipher_round_trips_without_persisting_plaintext(self):
        cipher = DjangoAesTokenCipher()
        encrypted = cipher.encrypt("provider-secret")

        self.assertNotIn("provider-secret", encrypted.value)
        self.assertEqual(cipher.decrypt(encrypted), "provider-secret")

    @override_settings(PLATFORM_WEBHOOK_SECRETS={"whatsapp": "local-test-secret"})
    def test_signature_verifier_accepts_only_valid_raw_body_hmac(self):
        body = b'{"messages":[]}'
        digest = hmac.new(b"local-test-secret", body, hashlib.sha256).hexdigest()
        verifier = DjangoWebhookSignatureVerifier()

        self.assertTrue(verifier.verify("whatsapp", body, f"sha256={digest}"))
        self.assertFalse(verifier.verify("whatsapp", body + b" ", f"sha256={digest}"))
        self.assertFalse(verifier.verify("instagram", body, f"sha256={digest}"))
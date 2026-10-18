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
from contexts.platform_connectors.infrastructure.adapters.environment_platform_gateway import (
    configured_platform_gateway,
)
from contexts.platform_connectors.infrastructure.adapters.mock_platform_gateway import (
    MockPlatformGateway,
)


class PlatformSecurityAdapterTests(unittest.TestCase):
    @override_settings(
        PLATFORM_TOKEN_ENCRYPTION_KEYS={"v1": base64.urlsafe_b64encode(b"k" * 32).decode()},
        PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION="v1",
    )
    def test_aes_cipher_round_trips_without_persisting_plaintext(self):
        cipher = DjangoAesTokenCipher()
        encrypted = cipher.encrypt("provider-secret")

        self.assertTrue(encrypted.value.startswith("v1."))
        self.assertNotIn("provider-secret", encrypted.value)
        self.assertEqual(cipher.decrypt(encrypted), "provider-secret")

    def test_cipher_decrypts_old_version_and_reencrypts_with_active_key(self):
        first_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        second_key = base64.urlsafe_b64encode(b"b" * 32).decode()
        with override_settings(
            PLATFORM_TOKEN_ENCRYPTION_KEYS={"v1": first_key},
            PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION="v1",
        ):
            old_token = DjangoAesTokenCipher().encrypt("provider-secret")

        with override_settings(
            PLATFORM_TOKEN_ENCRYPTION_KEYS={"v1": first_key, "v2": second_key},
            PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION="v2",
        ):
            rotating_cipher = DjangoAesTokenCipher()
            self.assertEqual(rotating_cipher.decrypt(old_token), "provider-secret")
            new_token = rotating_cipher.encrypt(rotating_cipher.decrypt(old_token))
            self.assertTrue(new_token.value.startswith("v2."))
            self.assertEqual(rotating_cipher.decrypt(new_token), "provider-secret")

    @override_settings(PLATFORM_WEBHOOK_SECRETS={"whatsapp": "local-test-secret"})
    def test_signature_verifier_accepts_only_valid_raw_body_hmac(self):
        body = b'{"messages":[]}'
        digest = hmac.new(b"local-test-secret", body, hashlib.sha256).hexdigest()
        verifier = DjangoWebhookSignatureVerifier()

        self.assertTrue(verifier.verify("whatsapp", body, f"sha256={digest}"))
        self.assertFalse(verifier.verify("whatsapp", body + b" ", f"sha256={digest}"))
        self.assertFalse(verifier.verify("instagram", body, f"sha256={digest}"))

    @override_settings(PLATFORM_ADAPTERS={"fake_channel": "mock"})
    def test_configured_gateway_uses_mock_adapter(self):
        self.assertIsInstance(configured_platform_gateway("fake_channel"), MockPlatformGateway)

    @override_settings(PLATFORM_ADAPTERS={"whatsapp": "real"})
    def test_configured_gateway_fails_closed_until_real_adapter_is_implemented(self):
        with self.assertRaisesRegex(RuntimeError, "real whatsapp adapter is not implemented"):
            configured_platform_gateway("whatsapp")
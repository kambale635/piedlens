import base64
import os
from io import StringIO
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.core.management import call_command
from django.test import TestCase, override_settings

from contexts.platform_connectors.domain.value_objects.encrypted_token import EncryptedToken
from contexts.platform_connectors.infrastructure.adapters.django_aes_token_cipher import (
    DjangoAesTokenCipher,
)
from contexts.platform_connectors.infrastructure.persistence.models import PlatformConnectionRecord


class PlatformTokenRotationTests(TestCase):
    def test_rotation_reencrypts_versioned_and_legacy_rows(self):
        first_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        second_key = base64.urlsafe_b64encode(b"b" * 32).decode()
        with override_settings(
            PLATFORM_TOKEN_ENCRYPTION_KEYS={"v1": first_key},
            PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION="v1",
        ):
            versioned_ciphertext = DjangoAesTokenCipher().encrypt("versioned-secret").value
        legacy_ciphertext = self._encrypt_legacy("legacy-secret", first_key)
        versioned_record = self._create_connection(versioned_ciphertext)
        legacy_record = self._create_connection(legacy_ciphertext)
        output = StringIO()

        with override_settings(
            PLATFORM_TOKEN_ENCRYPTION_KEYS={
                "legacy": first_key,
                "v1": first_key,
                "v2": second_key,
            },
            PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION="v2",
        ):
            call_command("rotate_platform_tokens", stdout=output)
            versioned_record.refresh_from_db()
            legacy_record.refresh_from_db()
            cipher = DjangoAesTokenCipher()

        versioned_token = EncryptedToken(versioned_record.encrypted_access_token)
        legacy_token = EncryptedToken(legacy_record.encrypted_access_token)
        self.assertEqual(cipher.key_version(versioned_token), "v2")
        self.assertEqual(cipher.key_version(legacy_token), "v2")
        self.assertEqual(cipher.decrypt(versioned_token), "versioned-secret")
        self.assertEqual(cipher.decrypt(legacy_token), "legacy-secret")
        self.assertEqual(output.getvalue(), "Rotated 2 platform token(s).\n")

    def _create_connection(self, encrypted_token):
        return PlatformConnectionRecord.objects.create(
            id=uuid4(),
            merchant_id=uuid4(),
            platform_type="whatsapp",
            external_account_id=str(uuid4()),
            encrypted_access_token=encrypted_token,
            status="active",
        )

    @staticmethod
    def _encrypt_legacy(plaintext, encoded_key):
        nonce = os.urandom(12)
        key = base64.urlsafe_b64decode(encoded_key.encode())
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode()
import base64
import unittest

from django.test import override_settings

from contexts.backup.infrastructure.persistence.django_backup_payload_cipher import (
    DjangoBackupPayloadCipher,
)


class BackupPayloadCipherTests(unittest.TestCase):
    def test_payload_round_trip_uses_authenticated_versioned_envelope(self):
        key = base64.urlsafe_b64encode(b"a" * 32).decode("ascii")
        with override_settings(
            BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION="v1",
            BACKUP_DATA_ENCRYPTION_KEYS={"v1": key},
        ):
            cipher = DjangoBackupPayloadCipher()
            payload = {"messages": [{"text": "private"}]}
            encrypted = cipher.encrypt(payload)

            self.assertNotIn("private", str(encrypted))
            self.assertEqual(cipher.key_version(encrypted), "v1")
            self.assertEqual(cipher.decrypt(encrypted), payload)

            tampered = {**encrypted, "ciphertext": encrypted["ciphertext"][:-4] + "AAAA"}
            with self.assertRaises(Exception):
                cipher.decrypt(tampered)

    def test_old_plaintext_payload_is_readable_for_lazy_migration(self):
        with override_settings(
            BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION="v1",
            BACKUP_DATA_ENCRYPTION_KEYS={
                "v1": base64.urlsafe_b64encode(b"b" * 32).decode("ascii")
            },
        ):
            cipher = DjangoBackupPayloadCipher()
            legacy_payload = {"messages": [{"text": "legacy"}]}

            self.assertIsNone(cipher.key_version(legacy_payload))
            self.assertEqual(cipher.decrypt(legacy_payload), legacy_payload)
            self.assertIn("_piedlens_encrypted_backup", cipher.encrypt(legacy_payload))


if __name__ == "__main__":
    unittest.main()
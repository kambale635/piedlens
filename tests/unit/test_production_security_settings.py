import base64
import unittest

from django.conf import settings

from config.security_settings import (
    REQUIRED_PRODUCTION_VARIABLES,
    validate_production_configuration,
)


class ProductionSecuritySettingsTests(unittest.TestCase):
    def _complete_environment(self):
        environment = {
            "DJANGO_ENV": "production",
            "DJANGO_DEBUG": "0",
            **{name: "configured" for name in REQUIRED_PRODUCTION_VARIABLES},
        }
        environment["PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION"] = "v1"
        environment["PLATFORM_TOKEN_ENCRYPTION_KEY_V1"] = base64.urlsafe_b64encode(
            b"k" * 32
        ).decode("ascii")
        environment["BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION"] = "v1"
        environment["BACKUP_DATA_ENCRYPTION_KEY_V1"] = base64.urlsafe_b64encode(
            b"b" * 32
        ).decode("ascii")
        environment["PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION"] = "v1"
        environment["PLATFORM_MESSAGE_ENCRYPTION_KEY_V1"] = base64.urlsafe_b64encode(
            b"m" * 32
        ).decode("ascii")
        environment["CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION"] = "v1"
        environment["CRM_MESSAGE_ENCRYPTION_KEY_V1"] = base64.urlsafe_b64encode(
            b"c" * 32
        ).decode("ascii")
        return environment

    def test_each_required_secret_is_rejected_when_missing(self):
        for name in REQUIRED_PRODUCTION_VARIABLES:
            with self.subTest(variable=name):
                environment = self._complete_environment()
                del environment[name]

                with self.assertRaisesRegex(RuntimeError, name):
                    validate_production_configuration(environment)

    def test_debug_is_rejected_in_production(self):
        environment = self._complete_environment()
        environment["DJANGO_DEBUG"] = "1"

        with self.assertRaisesRegex(RuntimeError, "DJANGO_DEBUG"):
            validate_production_configuration(environment)

    def test_s3_backend_requires_its_credentials(self):
        environment = self._complete_environment()
        environment["BACKUP_OBJECT_STORAGE_BACKEND"] = "s3"

        with self.assertRaisesRegex(RuntimeError, "BACKUP_S3_SECRET_ACCESS_KEY"):
            validate_production_configuration(environment)

    def test_active_token_key_must_be_valid_urlsafe_256_bit_key(self):
        environment = self._complete_environment()
        environment["PLATFORM_TOKEN_ENCRYPTION_KEY_V1"] = "invalid"

        with self.assertRaisesRegex(RuntimeError, "PLATFORM_TOKEN_ENCRYPTION_KEY_V1"):
            validate_production_configuration(environment)

    def test_backup_and_message_encryption_keys_are_required_and_valid(self):
        environment = self._complete_environment()
        del environment["BACKUP_DATA_ENCRYPTION_KEY_V1"]
        with self.assertRaisesRegex(RuntimeError, "BACKUP_DATA_ENCRYPTION_KEY_V1"):
            validate_production_configuration(environment)

        environment = self._complete_environment()
        environment["PLATFORM_MESSAGE_ENCRYPTION_KEY_V1"] = "invalid"
        with self.assertRaisesRegex(RuntimeError, "PLATFORM_MESSAGE_ENCRYPTION_KEY_V1"):
            validate_production_configuration(environment)

    def test_nonproduction_does_not_require_deployment_secrets(self):
        validate_production_configuration({"DJANGO_ENV": "development"})

    def test_webhook_secret_settings_cover_each_mock_supported_channel(self):
        self.assertEqual(
            set(settings.PLATFORM_WEBHOOK_SECRETS),
            {"whatsapp", "instagram", "facebook"},
        )


if __name__ == "__main__":
    unittest.main()
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from config.observability import initialize_sentry_if_configured


class ObservabilityTests(unittest.TestCase):
    def test_sentry_is_not_imported_when_dsn_is_empty(self):
        with patch.dict(os.environ, {"SENTRY_DSN": ""}):
            initialize_sentry_if_configured()

    def test_configured_sentry_uses_the_environment_dsn_without_networking(self):
        sentry_sdk = types.ModuleType("sentry_sdk")
        sentry_sdk.init = Mock()
        with (
            patch.dict(sys.modules, {"sentry_sdk": sentry_sdk}),
            patch.dict(
                os.environ,
                {"SENTRY_DSN": "https://public@example.invalid/1", "SENTRY_ENVIRONMENT": "staging"},
            ),
        ):
            initialize_sentry_if_configured()

        sentry_sdk.init.assert_called_once_with(
            dsn="https://public@example.invalid/1", environment="staging"
        )

    def test_configured_sentry_fails_clearly_when_sdk_is_unavailable(self):
        with (
            patch.dict(sys.modules, {"sentry_sdk": None}),
            patch.dict(os.environ, {"SENTRY_DSN": "https://public@example.invalid/1"}),
            self.assertRaisesRegex(RuntimeError, "sentry-sdk is not installed"),
        ):
            initialize_sentry_if_configured()


if __name__ == "__main__":
    unittest.main()
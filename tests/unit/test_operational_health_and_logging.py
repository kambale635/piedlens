import json
import logging
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase, override_settings

from piedlens_platform.health_views import live, metrics, ready
from piedlens_platform.logging import JsonLogFormatter
from piedlens_platform.worker_shutdown import GracefulShutdown


class OperationalHealthAndLoggingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_liveness_does_not_probe_dependencies(self):
        response = live(self.factory.get("/health/live"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"status": "live"})

    def test_readiness_reports_database_and_redis_status_without_error_details(self):
        client = Mock()
        with patch("piedlens_platform.health_views._redis_client", return_value=client):
            response = ready(self.factory.get("/health/ready"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"status": "ready", "failedChecks": []})
        client.ping.assert_called_once_with()

    def test_readiness_returns_503_when_redis_is_unavailable(self):
        client = Mock()
        client.ping.side_effect = ConnectionError("private redis endpoint")
        with patch("piedlens_platform.health_views._redis_client", return_value=client):
            response = ready(self.factory.get("/health/ready"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.content)["failedChecks"], ["redis"])
        self.assertNotIn("private redis endpoint", response.content.decode())

    @override_settings(
        HEALTH_OUTBOX_LAG_ALERT_SECONDS=10,
        HEALTH_DLQ_SIZE_ALERT_THRESHOLD=2,
        PIEDLENS_ALERT_HOOK="",
        HEALTH_METRICS_TOKEN="metrics-test-token",
    )
    def test_metrics_return_outbox_and_dlq_values(self):
        with (
            patch(
                "piedlens_platform.health_views._outbox_lag_seconds",
                return_value={"crm": 4},
            ),
            patch(
                "piedlens_platform.health_views._dead_letter_sizes",
                return_value={"crm.dlq": 1},
            ),
        ):
            response = metrics(
                self.factory.get("/health/metrics", HTTP_AUTHORIZATION="Bearer metrics-test-token")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {
                "status": "ok",
                "outboxLagSeconds": {"crm": 4},
                "deadLetterQueueSizes": {"crm.dlq": 1},
            },
        )

    @override_settings(
        HEALTH_OUTBOX_LAG_ALERT_SECONDS=10,
        HEALTH_DLQ_SIZE_ALERT_THRESHOLD=2,
        PIEDLENS_ALERT_HOOK="tests.unit.test_operational_health_and_logging.alert_sink",
        HEALTH_METRICS_TOKEN="metrics-test-token",
    )
    def test_metric_thresholds_invoke_the_configured_alert_hook(self):
        sink = Mock()
        with (
            patch(
                "piedlens_platform.health_views._outbox_lag_seconds",
                return_value={"crm": 15},
            ),
            patch(
                "piedlens_platform.health_views._dead_letter_sizes",
                return_value={"crm.dlq": 2},
            ),
            patch("tests.unit.test_operational_health_and_logging.alert_sink", sink, create=True),
        ):
            response = metrics(
                self.factory.get("/health/metrics", HTTP_AUTHORIZATION="Bearer metrics-test-token")
            )

        self.assertEqual(response.status_code, 200)
        sink.assert_called_once()
        alerts = sink.call_args.args[0]["alerts"]
        self.assertEqual({item["type"] for item in alerts}, {"outbox_lag", "dead_letter_queue"})

    @override_settings(HEALTH_METRICS_TOKEN="metrics-test-token")
    def test_metrics_require_the_dedicated_bearer_token(self):
        response = metrics(self.factory.get("/health/metrics"))

        self.assertEqual(response.status_code, 401)

    @override_settings(
        HEALTH_OUTBOX_LAG_ALERT_SECONDS=1,
        HEALTH_DLQ_SIZE_ALERT_THRESHOLD=1,
        HEALTH_METRICS_TOKEN="metrics-test-token",
        PIEDLENS_ALERT_HOOK="tests.unit.test_operational_health_and_logging.alert_sink",
    )
    def test_alert_hook_failure_does_not_break_metrics_response(self):
        with (
            patch(
                "piedlens_platform.health_views._outbox_lag_seconds",
                return_value={"crm": 10},
            ),
            patch(
                "piedlens_platform.health_views._dead_letter_sizes",
                return_value={"crm.dlq": 2},
            ),
            patch("piedlens_platform.health_views.import_string", side_effect=RuntimeError("hook")),
        ):
            response = metrics(
                self.factory.get("/health/metrics", HTTP_AUTHORIZATION="Bearer metrics-test-token")
            )

        self.assertEqual(response.status_code, 200)

    def test_json_formatter_emits_correlation_and_allowlisted_metadata(self):
        record = logging.LogRecord("test", logging.INFO, "", 0, "request accepted", (), None)
        record.correlation_id = "correlation-1"
        record.merchant_id = "merchant-1"
        record.secret = "must-not-be-serialized"

        output = JsonLogFormatter().format(record)
        payload = json.loads(output)

        self.assertEqual(payload["correlationId"], "correlation-1")
        self.assertEqual(payload["merchant_id"], "merchant-1")
        self.assertNotIn("secret", payload)

    def test_worker_shutdown_wait_is_interruptible(self):
        with patch("piedlens_platform.worker_shutdown.signal.signal") as register:
            with GracefulShutdown() as shutdown:
                handlers = [call.args[1] for call in register.call_args_list]
                self.assertEqual(len(handlers), 2)
                self.assertFalse(shutdown.stop_requested)
                handlers[0](None, None)
                self.assertTrue(shutdown.stop_requested)
                self.assertTrue(shutdown.wait(0))


def alert_sink(event):
    raise AssertionError("Test hook should be patched before use.")
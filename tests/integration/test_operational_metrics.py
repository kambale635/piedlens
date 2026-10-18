import json
from datetime import timedelta
from uuid import uuid4

import redis
from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from contexts.crm.infrastructure.persistence.models import OutboxEventRecord
from piedlens_platform.health_views import metrics


class OperationalMetricsIntegrationTests(TestCase):
    @override_settings(
        HEALTH_METRICS_TOKEN="metrics-integration-token",
        HEALTH_OUTBOX_LAG_ALERT_SECONDS=1,
        HEALTH_DLQ_SIZE_ALERT_THRESHOLD=1,
        PIEDLENS_ALERT_HOOK="tests.integration.test_operational_metrics.capture_alert",
    )
    def test_metrics_read_outbox_and_real_redis_dlq_and_emit_alert(self):
        from unittest.mock import patch

        occurred_at = timezone.now() - timedelta(seconds=30)
        OutboxEventRecord.objects.create(
            event_id=uuid4(),
            event_type="OperationalMetricProbe",
            occurred_at=occurred_at,
            payload={},
        )
        stream_name = f"crm.dlq:{uuid4()}"
        redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        redis_client.xadd(stream_name, {"probe": "1"})
        events = []
        request = RequestFactory().get(
            "/health/metrics", HTTP_AUTHORIZATION="Bearer metrics-integration-token"
        )

        def measured_dlq_sizes():
            return {"crm.dlq": redis_client.xlen(stream_name)}

        try:
            with (
                patch("piedlens_platform.health_views._dead_letter_sizes", measured_dlq_sizes),
                patch("tests.integration.test_operational_metrics.capture_alert", events.append),
            ):
                response = metrics(request)
        finally:
            redis_client.delete(stream_name)

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertGreaterEqual(body["outboxLagSeconds"]["crm"], 30)
        self.assertEqual(body["deadLetterQueueSizes"]["crm.dlq"], 1)
        self.assertTrue(events[0]["alerts"])


def capture_alert(event):
    raise AssertionError("Test alert hook should be patched before use.")
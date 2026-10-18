from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.test import TransactionTestCase
from django.conf import settings
import redis
from redis.exceptions import RedisError

from contexts.crm.infrastructure.persistence.models import OutboxEventRecord
from piedlens_platform.event_bus.outbox_relay_worker import OutboxRelayWorker
from piedlens_platform.event_bus.redis_stream_publisher import RedisStreamEventPublisher


class OutboxRelayIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        self.event = OutboxEventRecord.objects.create(
            event_id=uuid4(),
            event_type="ContactChanged",
            occurred_at=self.now,
            produced_by="crm",
            payload={"contact_id": str(uuid4())},
        )
        self.stream = f"test:relay:{uuid4()}.events"
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL)
        try:
            self.redis_client.ping()
        except RedisError as error:
            self.fail(
                "Redis integration test cannot connect; verify REDIS_URL and Redis availability: "
                f"{error}"
            )

    def tearDown(self):
        self.redis_client.delete(self.stream)

    def test_outbox_event_is_relayed_to_real_redis_stream(self):
        worker = OutboxRelayWorker(
            OutboxEventRecord,
            RedisStreamEventPublisher(self.redis_client, self.stream),
            10,
            2,
            60,
        )

        published = worker.publish_batch()
        entries = self.redis_client.xrange(self.stream)

        self.assertEqual(published, 1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1][b"envelope"].decode().count('"eventId"'), 1)
        self.event.refresh_from_db()
        self.assertIsNotNone(self.event.published_at)

    def test_publish_marks_outbox_event_only_after_successful_xadd(self):
        class Publisher:
            def __init__(self):
                self.envelopes = []

            def publish(self, envelope):
                self.envelopes.append(envelope)

        publisher = Publisher()
        worker = OutboxRelayWorker(OutboxEventRecord, publisher, 10, 2, 60)

        with patch("piedlens_platform.event_bus.outbox_relay_worker.timezone.now", return_value=self.now):
            published = worker.publish_batch()

        self.assertEqual(published, 1)
        self.event.refresh_from_db()
        self.assertEqual(self.event.published_at, self.now)
        self.assertIsNone(self.event.next_attempt_at)
        self.assertEqual(publisher.envelopes[0]["eventId"], str(self.event.event_id))
        self.assertEqual(publisher.envelopes[0]["payload"], self.event.payload)

    def test_redis_failure_schedules_bounded_retry_without_marking_published(self):
        class Publisher:
            def publish(self, envelope):
                raise RedisError("redis unavailable")

        worker = OutboxRelayWorker(OutboxEventRecord, Publisher(), 10, 2, 60)

        with patch("piedlens_platform.event_bus.outbox_relay_worker.timezone.now", return_value=self.now):
            published = worker.publish_batch()

        self.assertEqual(published, 0)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.published_at)
        self.assertEqual(self.event.attempts, 1)
        self.assertEqual((self.event.next_attempt_at - self.now).total_seconds(), 2)
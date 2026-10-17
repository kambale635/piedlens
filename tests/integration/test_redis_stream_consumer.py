import os
import unittest
from uuid import uuid4

import redis

from piedlens_platform.event_bus.stream_consumer_worker import RedisStreamConsumerWorker


class RedisStreamConsumerIntegrationTests(unittest.TestCase):
    def setUp(self):
        redis_url = (
            os.environ.get("REDIS_INTEGRATION_URL")
            or os.environ.get("REDIS_URL")
            or "redis://localhost:6379/0"
        )
        self.client = redis.Redis.from_url(redis_url)
        try:
            self.client.ping()
        except redis.RedisError as error:
            self.fail(
                "Redis integration test cannot connect; verify REDIS_URL and Redis availability: "
                f"{error}"
            )
        self.stream = f"test:{uuid4()}.events"
        self.group = f"test:{uuid4()}"
        self.client.xadd(self.stream, {"envelope": '{"eventId":"e-1"}'})

    def tearDown(self):
        self.client.delete(
            self.stream,
            f"{self.stream}:{self.group}:failures",
            f"{self.group}.dlq",
        )

    def test_unacked_failure_is_claimed_and_successful_effect_runs_once(self):
        attempts = []

        def handler(envelope):
            if not attempts:
                attempts.append("failed")
                raise RuntimeError("simulated crash before acknowledgement")
            if "effect" not in attempts:
                attempts.append("effect")

        worker = RedisStreamConsumerWorker(
            self.client,
            self.stream,
            self.group,
            "integration-worker",
            handler,
            claim_idle_ms=0,
        )
        worker.process_once(block_ms=1)
        self.assertEqual(self.client.xpending(self.stream, self.group)["pending"], 1)

        worker.process_once(block_ms=1)
        self.assertEqual(attempts, ["failed", "effect"])
        self.assertEqual(self.client.xpending(self.stream, self.group)["pending"], 0)

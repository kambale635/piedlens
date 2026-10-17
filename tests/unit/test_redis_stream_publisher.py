import json
import unittest

from piedlens_platform.event_bus.redis_stream_publisher import RedisStreamEventPublisher


class RedisStreamEventPublisherTests(unittest.TestCase):
    def test_publish_appends_one_versioned_envelope_field(self):
        class RedisStub:
            def xadd(self, stream, fields):
                self.stream = stream
                self.fields = fields
                return b"1-0"

        redis_client = RedisStub()
        publisher = RedisStreamEventPublisher(redis_client, "crm.events")

        stream_id = publisher.publish({"eventId": "event-1", "payload": {"value": 3}})

        self.assertEqual(stream_id, "1-0")
        self.assertEqual(redis_client.stream, "crm.events")
        self.assertEqual(
            json.loads(redis_client.fields["envelope"]),
            {"eventId": "event-1", "payload": {"value": 3}},
        )
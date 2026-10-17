"""Publish versioned Outbox envelopes to one context-owned Redis Stream.

Only an Outbox relay may call this adapter; Use Cases persist to PostgreSQL
under INV-TR-02. See docs/14-event-driven-architecture.md.
"""

import json

from django.core.serializers.json import DjangoJSONEncoder


class RedisStreamEventPublisher:
	"""Write event envelopes to the Redis Stream owned by a producer context."""

	def __init__(self, redis_client, stream_name: str) -> None:
		self._redis = redis_client
		self._stream_name = stream_name

	def publish(self, envelope: dict) -> str:
		"""Append the complete envelope as one JSON field and return its stream ID."""
		stream_id = self._redis.xadd(
			self._stream_name,
			{"envelope": json.dumps(envelope, cls=DjangoJSONEncoder, separators=(",", ":"))},
		)
		return stream_id.decode("utf-8") if isinstance(stream_id, bytes) else str(stream_id)
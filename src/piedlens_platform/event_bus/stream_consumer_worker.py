"""Consume Redis Stream groups with post-commit acknowledgement and a DLQ."""

import json

from redis.exceptions import ResponseError, RedisError


class RedisStreamConsumerWorker:
    """Dispatch events at least once and dead-letter after bounded failures."""

    def __init__(
        self,
        redis_client,
        stream_name: str,
        consumer_context: str,
        consumer_name: str,
        handler,
        claim_idle_ms: int,
        max_deliveries: int = 5,
    ) -> None:
        self._redis = redis_client
        self._stream = stream_name
        self._group = consumer_context
        self._consumer = consumer_name
        self._handler = handler
        self._claim_idle_ms = claim_idle_ms
        self._max_deliveries = max_deliveries
        self._failure_key = f"{stream_name}:{consumer_context}:failures"
        self._dead_letter_stream = f"{consumer_context}.dlq"

    def ensure_group(self) -> None:
        """Create a durable group at the start of the stream if it is absent."""
        try:
            self._redis.xgroup_create(self._stream, self._group, id="0-0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    def process_once(self, block_ms: int = 1000) -> int:
        """Claim stale pending entries first, then read new messages from the group."""
        self.ensure_group()
        claimed = self._redis.xautoclaim(
            self._stream,
            self._group,
            self._consumer,
            min_idle_time=self._claim_idle_ms,
            start_id="0-0",
            count=10,
        )
        entries = claimed[1] if claimed and len(claimed) > 1 else []
        if not entries:
            batches = self._redis.xreadgroup(
                self._group,
                self._consumer,
                {self._stream: ">"},
                count=10,
                block=block_ms,
            )
            entries = [entry for _, stream_entries in batches for entry in stream_entries]
        processed = 0
        for message_id, fields in entries:
            self._process_entry(message_id, fields)
            processed += 1
        return processed

    def _process_entry(self, message_id, fields) -> None:
        """Ack only after handler commit, or after durable dead-letter publication."""
        try:
            raw_envelope = fields.get(b"envelope", fields.get("envelope"))
            envelope = json.loads(raw_envelope)
            self._handler(envelope)
        except Exception as error:
            failure_count = self._redis.hincrby(self._failure_key, message_id, 1)
            if failure_count < self._max_deliveries:
                return
            self._redis.xadd(
                self._dead_letter_stream,
                {
                    "envelope": raw_envelope if "raw_envelope" in locals() else "{}",
                    "sourceStream": self._stream,
                    "sourceMessageId": message_id,
                    "failureType": type(error).__name__,
                },
            )
            self._redis.xack(self._stream, self._group, message_id)
            self._redis.hdel(self._failure_key, message_id)
            return
        self._redis.xack(self._stream, self._group, message_id)
        self._redis.hdel(self._failure_key, message_id)
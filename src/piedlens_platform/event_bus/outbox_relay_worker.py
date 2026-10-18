"""Relay committed context Outbox rows to Redis Streams (INV-TR-02)."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from redis.exceptions import RedisError


class OutboxRelayWorker:
	"""Publish locked Outbox batches and persist retry scheduling per event."""

	def __init__(
		self,
		outbox_model,
		publisher,
		batch_size: int,
		backoff_base_seconds: float,
		backoff_max_seconds: float,
		payload_transformer=None,
	) -> None:
		self._outbox_model = outbox_model
		self._publisher = publisher
		self._batch_size = batch_size
		self._backoff_base_seconds = backoff_base_seconds
		self._backoff_max_seconds = backoff_max_seconds
		self._payload_transformer = payload_transformer or (lambda event_type, payload: payload)

	def publish_batch(self) -> int:
		"""Publish one eligible batch; locked rows are skipped by competing relays."""
		now = timezone.now()
		published = 0
		with transaction.atomic():
			events = list(
				self._outbox_model.objects.filter(
					published_at__isnull=True,
				).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
				.order_by("occurred_at", "event_id")
				.select_for_update(skip_locked=True)[: self._batch_size]
			)
			for event in events:
				try:
					self._publisher.publish(
						{
							"eventId": str(event.event_id),
							"eventType": event.event_type,
							"eventVersion": event.event_version,
							"occurredAt": event.occurred_at.isoformat(),
							"producedBy": event.produced_by,
							"correlationId": (
								str(event.correlation_id) if event.correlation_id else None
							),
							"payload": self._payload_transformer(event.event_type, event.payload),
						}
					)
				except RedisError:
					event.attempts += 1
					delay = min(
						self._backoff_base_seconds * (2 ** (event.attempts - 1)),
						self._backoff_max_seconds,
					)
					event.next_attempt_at = now + timedelta(seconds=delay)
					event.save(update_fields=["attempts", "next_attempt_at"])
					continue

				event.published_at = now
				event.next_attempt_at = None
				event.save(update_fields=["published_at", "next_attempt_at"])
				published += 1
		return published
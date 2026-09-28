"""Module: contexts/order_detection/infrastructure/django_order_detection_outbox.py
Context: Order Detection.
Role: persist domain events for asynchronous relay to Redis Streams.

This adapter only writes PostgreSQL outbox rows. It never publishes directly to Redis;
the outbox relay is responsible for delivery (INV-TR-02).
"""

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .models import OutboxEventRecord


class DjangoOrderDetectionOutbox:
    """Append Order Detection events to the active Django database transaction."""

    def add(self, event: object) -> None:
        """Persist a versioned event envelope; caller owns the atomic UnitOfWork."""
        event_id = getattr(event, "event_id", uuid4())
        occurred_at = getattr(event, "occurred_at", datetime.now(timezone.utc))
        payload = self._serialize(event)
        payload.pop("event_id", None)
        payload.pop("occurred_at", None)
        OutboxEventRecord.objects.create(
            event_id=event_id,
            event_type=type(event).__name__,
            event_version=1,
            occurred_at=occurred_at,
            produced_by="order-detection",
            correlation_id=getattr(event, "correlation_id", None),
            payload=payload,
        )

    @classmethod
    def _serialize(cls, value: Any) -> Any:
        """Convert immutable domain-event values to JSON-compatible payload data."""
        if is_dataclass(value):
            return {field.name: cls._serialize(getattr(value, field.name)) for field in fields(value)}
        if isinstance(value, (UUID, Decimal)):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, tuple):
            return [cls._serialize(item) for item in value]
        if isinstance(value, list):
            return [cls._serialize(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._serialize(item) for key, item in value.items()}
        return value
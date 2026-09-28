"""Module: contexts/crm/infrastructure/django_crm_outbox.py
Context: CRM.
Role: persist CRM events for asynchronous relay to Redis Streams (INV-TR-02).

This adapter only writes the CRM Outbox table; the relay publishes events outside
the request/use-case transaction.
"""

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .models import OutboxEventRecord


class DjangoCRMOutbox:
    """Append CRM domain events to the active Django database transaction."""

    def add(self, event: object) -> None:
        """Persist a versioned event envelope in the caller's UnitOfWork (INV-TR-02)."""
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
            produced_by="crm",
            correlation_id=getattr(event, "correlation_id", None),
            payload=payload,
        )

    @classmethod
    def _serialize(cls, value: Any) -> Any:
        """Convert immutable event values to JSON-compatible payload data."""
        if is_dataclass(value):
            return {
                field.name: cls._serialize(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, (UUID, Decimal)):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (tuple, list)):
            return [cls._serialize(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._serialize(item) for key, item in value.items()}
        return value
import json
from dataclasses import fields, is_dataclass

from django.core.serializers.json import DjangoJSONEncoder

from .models import OutboxEventRecord


class DjangoPlatformConnectorsOutbox:
    """Write normalized producer events to PostgreSQL for the future Outbox relay (INV-TR-02)."""

    def add(self, event: object) -> None:
        """Insert an event envelope in the active aggregate transaction."""
        if not is_dataclass(event):
            raise TypeError("Outbox events must be dataclass instances.")
        values = {item.name: getattr(event, item.name) for item in fields(event)}
        event_id = values.pop("event_id")
        occurred_at = values.pop("occurred_at")
        event_type = type(event).__name__
        OutboxEventRecord.objects.create(
            event_id=event_id,
            event_type=event_type,
            occurred_at=occurred_at,
            payload=json.loads(DjangoJSONEncoder().encode(values)),
        )
import json
from dataclasses import fields, is_dataclass

from django.core.serializers.json import DjangoJSONEncoder

from ..persistence.models import OutboxEventRecord


class DjangoRulesEngineOutbox:
    """Persist Rule events for deferred publication by the future Outbox relay (INV-TR-02)."""

    def add(self, event: object) -> None:
        """Insert an event envelope into the active Rules Engine transaction."""
        if not is_dataclass(event):
            raise TypeError("Outbox events must be dataclass instances.")
        values = {item.name: getattr(event, item.name) for item in fields(event)}
        event_id = values.pop("event_id")
        occurred_at = values.pop("occurred_at")
        OutboxEventRecord.objects.create(
            event_id=event_id,
            event_type=type(event).__name__,
            occurred_at=occurred_at,
            payload=json.loads(DjangoJSONEncoder().encode(values)),
        )
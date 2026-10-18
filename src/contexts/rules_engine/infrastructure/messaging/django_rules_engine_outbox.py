import json
from dataclasses import fields, is_dataclass
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from shared_kernel.value_objects.money import Money

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
        values["extracted_data"] = self._serialize_money(values.get("extracted_data", {}))
        OutboxEventRecord.objects.create(
            event_id=event_id,
            event_type=type(event).__name__,
            occurred_at=occurred_at,
            payload=json.loads(DjangoJSONEncoder().encode(values)),
        )

    @classmethod
    def _serialize_money(cls, value):
        """Serialize shared Money values as the stable amount/currency event contract."""
        if isinstance(value, Money):
            return {"amount": str(value.amount), "currency": value.currency}
        if isinstance(value, dict):
            return {key: cls._serialize_money(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._serialize_money(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        return value
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from ..persistence.models import OutboxEventRecord


class DjangoAccessControlOutbox:
    def add(self, event: object) -> None:
        event_id = getattr(event, "event_id", uuid4())
        occurred_at = getattr(event, "occurred_at", datetime.now().astimezone())
        payload = self._serialize(event)
        payload.pop("event_id", None)
        payload.pop("occurred_at", None)
        OutboxEventRecord.objects.create(
            event_id=event_id,
            event_type=type(event).__name__,
            occurred_at=occurred_at,
            produced_by="access_control",
            payload=payload,
        )

    @classmethod
    def _serialize(cls, value: Any) -> Any:
        if is_dataclass(value):
            return {field.name: cls._serialize(getattr(value, field.name)) for field in fields(value)}
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
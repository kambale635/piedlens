from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class MessageEvaluated:
    """Outbox event carrying a normalized, configuration-derived evaluation result."""

    merchant_id: UUID
    message_id: UUID
    confidence_score: int
    matched_rule_ids: tuple[UUID, ...]
    extracted_data: dict
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)
    platform_connection_id: UUID | None = None
    external_sender_id: str | None = None
    display_name: str = ""
    message_event_id: UUID | None = None
    source_message_timestamp: datetime | None = None
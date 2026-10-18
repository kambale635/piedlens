from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class MerchantDataPurged:
    """CRM confirmation that all local merchant-owned records were purged (INV-CRM-09)."""

    context: str
    merchant_id: UUID
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class UserRegistered:
    user_id: UUID
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MerchantRegistered:
    merchant_id: UUID
    owner_user_id: UUID
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MerchantPlanChanged:
    merchant_id: UUID
    subscription_plan: str
    effective_at: datetime
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MerchantDataPurged:
    """Identity confirmation that its local merchant data purge completed (INV-BK-06)."""

    context: str
    merchant_id: UUID
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)
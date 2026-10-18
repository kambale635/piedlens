from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class RolePermissionsChanged:
    role_id: UUID
    permissions: tuple[str, ...]
    changed_by: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RoleAssigned:
    role_assignment_id: UUID
    user_id: UUID
    role_id: UUID
    scope_type: str
    scope_id: UUID | None
    granted_by: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RoleRevoked:
    role_assignment_id: UUID
    revoked_by: str
    revoked_at: datetime
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MerchantDataPurged:
    """Access Control confirmation that local merchant assignments were purged (INV-AC-06)."""

    context: str
    merchant_id: UUID
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)
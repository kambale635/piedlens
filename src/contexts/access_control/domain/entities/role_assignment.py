from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RoleAssignment:
    id: UUID
    user_id: UUID
    role_id: UUID
    scope_type: str
    scope_id: UUID | None
    granted_by: str
    granted_at: datetime
    revoked_by: str | None = None
    revoked_at: datetime | None = None

    def revoke(self, revoked_by: UUID, revoked_at: datetime) -> "RoleAssignment":
        return RoleAssignment(
            self.id, self.user_id, self.role_id, self.scope_type, self.scope_id,
            self.granted_by, self.granted_at, str(revoked_by), revoked_at,
        )
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Role:
    id: UUID
    name: str
    permissions: frozenset[str]
    is_system: bool
    created_at: datetime
    created_by: str = "system"
    updated_by: str | None = None

    def with_permissions(self, permissions: set[str] | frozenset[str], updated_by: str) -> "Role":
        return Role(
            self.id, self.name, frozenset(permissions), self.is_system,
            self.created_at, self.created_by, updated_by,
        )
from uuid import uuid4

from ...domain.entities.role import Role
from ..exceptions.access_control_exceptions import RoleNameAlreadyExists, UnknownPermission
from ..ports.access_control_ports import (
    IAccessControlClock,
    IAccessControlRepository,
    IPermissionCatalog,
)


class CreateRoleUseCase:
    """Create a role only from permissions declared by actual routes (INV-AC-01)."""

    def __init__(self, roles: IAccessControlRepository, catalog: IPermissionCatalog,
                 clock: IAccessControlClock) -> None:
        self.roles = roles
        self.catalog = catalog
        self.clock = clock

    def execute(self, name: str, permissions: list[str], created_by="system") -> dict:
        """Persist a uniquely named role with a validated permission set."""
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Role name must not be empty.")
        if self.roles.find_role_by_name(normalized_name):
            raise RoleNameAlreadyExists()
        unknown = set(permissions) - self.catalog.declared_permissions()
        if unknown:
            raise UnknownPermission()
        role = Role(
            uuid4(), normalized_name, frozenset(permissions), False,
            self.clock.now_utc(), str(created_by),
        )
        self.roles.save_role(role)
        return {"roleId": role.id}
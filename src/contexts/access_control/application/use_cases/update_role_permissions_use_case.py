from uuid import UUID

from ...domain.events.access_control_events import RolePermissionsChanged
from ..exceptions.access_control_exceptions import RoleNotFound, UnknownPermission
from ..ports.access_control_ports import (
    IAccessControlOutbox,
    IAccessControlRepository,
    IAccessControlUnitOfWork,
    IPermissionCache,
    IPermissionCatalog,
)


class UpdateRolePermissionsUseCase:
    """Replace a role's permissions and invalidate cached decisions immediately (INV-AC-05)."""

    def __init__(self, roles: IAccessControlRepository, catalog: IPermissionCatalog,
                 cache: IPermissionCache, outbox: IAccessControlOutbox,
                 unit_of_work: IAccessControlUnitOfWork) -> None:
        self.roles = roles
        self.catalog = catalog
        self.cache = cache
        self.outbox = outbox
        self.unit_of_work = unit_of_work

    def execute(self, role_id: UUID, permissions: list[str], changed_by="system") -> dict:
        """Persist the role mutation and its event as one transaction (INV-AC-04/05)."""
        role = self.roles.find_role(role_id)
        if role is None:
            raise RoleNotFound()
        if role.is_system:
            raise ValueError("System roles cannot be changed through this use case.")
        if set(permissions) - self.catalog.declared_permissions():
            raise UnknownPermission()
        updated = role.with_permissions(frozenset(permissions), str(changed_by))
        with self.unit_of_work:
            self.roles.save_role(updated)
            self.outbox.add(RolePermissionsChanged(
                role.id, tuple(sorted(updated.permissions)), str(changed_by)
            ))
        self.cache.invalidate_all()
        return {"roleId": role.id, "permissions": sorted(updated.permissions)}
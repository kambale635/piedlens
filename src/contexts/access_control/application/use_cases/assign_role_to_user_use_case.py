from uuid import UUID, uuid4

from ...domain.entities.role_assignment import RoleAssignment
from ...domain.events.access_control_events import RoleAssigned
from ...domain.exceptions.access_control_exceptions import InsufficientPrivilegeToGrant
from ..exceptions.access_control_exceptions import RoleNotFound
from ..ports.access_control_ports import (
    IAccessControlClock,
    IAccessControlOutbox,
    IAccessControlRepository,
    IAccessControlUnitOfWork,
    IPermissionCache,
)


class AssignRoleToUserUseCase:
    """Assign only permissions the actor already holds on the same scope (INV-AC-02/04)."""

    def __init__(self, roles: IAccessControlRepository, clock: IAccessControlClock,
                 cache: IPermissionCache, outbox: IAccessControlOutbox,
                 unit_of_work: IAccessControlUnitOfWork) -> None:
        self.roles = roles
        self.clock = clock
        self.cache = cache
        self.outbox = outbox
        self.unit_of_work = unit_of_work

    def execute(self, user_id: UUID, role_id: UUID, scope, granted_by: UUID) -> dict:
        """Record the grant actor and time, preventing permission escalation (INV-AC-02/04)."""
        role = self.roles.find_role(role_id)
        if role is None:
            raise RoleNotFound()
        scope_type, scope_id = self._scope(scope)
        own_permissions = self.roles.permissions_for(granted_by, scope_type, scope_id)
        if not role.permissions.issubset(own_permissions):
            raise InsufficientPrivilegeToGrant()
        assignment = RoleAssignment(
            uuid4(), user_id, role_id, scope_type, scope_id, str(granted_by), self.clock.now_utc()
        )
        with self.unit_of_work:
            self.roles.save_assignment(assignment)
            self.outbox.add(RoleAssigned(
                assignment.id, user_id, role_id, scope_type, scope_id, str(granted_by)
            ))
        self.cache.invalidate_all()
        return {"roleAssignmentId": assignment.id}

    @staticmethod
    def _scope(scope) -> tuple[str, UUID | None]:
        if scope == "global":
            return "global", None
        if isinstance(scope, dict) and scope.get("merchantId"):
            return "merchant", UUID(str(scope["merchantId"]))
        if isinstance(scope, UUID):
            return "merchant", scope
        raise ValueError("Scope must be global or contain a merchantId.")
from uuid import UUID

from ...domain.events.access_control_events import RoleRevoked
from ..exceptions.access_control_exceptions import RoleAssignmentNotFound
from ..ports.access_control_ports import (
    IAccessControlClock,
    IAccessControlOutbox,
    IAccessControlRepository,
    IAccessControlUnitOfWork,
    IPermissionCache,
)


class RevokeRoleFromUserUseCase:
    """Revoke an assignment with actor/time audit and immediate cache invalidation (INV-AC-04/05)."""

    def __init__(self, roles: IAccessControlRepository, clock: IAccessControlClock,
                 cache: IPermissionCache, outbox: IAccessControlOutbox,
                 unit_of_work: IAccessControlUnitOfWork) -> None:
        self.roles = roles
        self.clock = clock
        self.cache = cache
        self.outbox = outbox
        self.unit_of_work = unit_of_work

    def execute(self, role_assignment_id: UUID, revoked_by: UUID) -> dict:
        """Persist a traceable revocation and invalidate all cached permission decisions."""
        assignment = self.roles.find_assignment(role_assignment_id)
        if assignment is None or assignment.revoked_at is not None:
            raise RoleAssignmentNotFound()
        revoked_at = self.clock.now_utc()
        revoked = assignment.revoke(revoked_by, revoked_at)
        with self.unit_of_work:
            self.roles.save_assignment(revoked)
            self.outbox.add(RoleRevoked(role_assignment_id, str(revoked_by), revoked_at))
        self.cache.invalidate_all()
        return {"revokedAt": revoked_at}
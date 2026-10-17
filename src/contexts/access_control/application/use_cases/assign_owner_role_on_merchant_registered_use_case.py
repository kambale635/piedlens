from uuid import UUID, uuid4

from ...domain.entities.role_assignment import RoleAssignment
from ...domain.events.access_control_events import RoleAssigned
from ..exceptions.access_control_exceptions import RoleNotFound
from ..ports.access_control_ports import (
    IAccessControlClock,
    IAccessControlOutbox,
    IAccessControlRepository,
    IAccessControlUnitOfWork,
    IProcessedEventRepository,
    IPermissionCache,
)


class AssignOwnerRoleOnMerchantRegisteredUseCase:
    """Idempotently assign the system Owner role for a registered merchant (INV-ID-06/AC-04)."""

    def __init__(self, roles: IAccessControlRepository, clock: IAccessControlClock,
                 cache: IPermissionCache, outbox: IAccessControlOutbox,
                 unit_of_work: IAccessControlUnitOfWork,
                 processed_events: IProcessedEventRepository | None = None) -> None:
        self.roles = roles
        self.clock = clock
        self.cache = cache
        self.outbox = outbox
        self.unit_of_work = unit_of_work
        self.processed_events = processed_events

    def execute(self, merchant_id: UUID, owner_user_id: UUID, event_id: UUID | None = None) -> dict:
        """Create one scoped Owner RoleAssignment, attributed to system (INV-AC-04)."""
        role = self.roles.find_role_by_name("Owner")
        if role is None:
            raise RoleNotFound()
        consumer_name = type(self).__name__
        with self.unit_of_work:
            if event_id and self.processed_events and self.processed_events.has_processed(
                event_id, consumer_name
            ):
                existing = self.roles.find_active_assignment(owner_user_id, role.id, merchant_id)
                return {"roleAssignmentId": existing.id if existing else None}
            existing = self.roles.find_active_assignment(owner_user_id, role.id, merchant_id)
            if existing is not None:
                if event_id and self.processed_events:
                    self.processed_events.mark_processed(event_id, consumer_name)
                return {"roleAssignmentId": existing.id}
            assignment = RoleAssignment(
                uuid4(), owner_user_id, role.id, "merchant", merchant_id, "system", self.clock.now_utc()
            )
            self.roles.save_assignment(assignment)
            self.outbox.add(RoleAssigned(
                assignment.id, owner_user_id, role.id, "merchant", merchant_id, "system"
            ))
            if event_id and self.processed_events:
                self.processed_events.mark_processed(event_id, consumer_name)
        self.cache.invalidate_all()
        return {"roleAssignmentId": assignment.id}
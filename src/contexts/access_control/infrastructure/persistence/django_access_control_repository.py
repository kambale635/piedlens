from django.db.models import Q

from contexts.access_control.domain.entities.role import Role
from contexts.access_control.domain.entities.role_assignment import RoleAssignment
from .models import RoleAssignmentRecord, RoleRecord


class DjangoAccessControlRepository:
    def find_role(self, role_id):
        record = RoleRecord.objects.filter(id=role_id).first()
        return self._role(record) if record else None

    def find_role_by_name(self, name):
        record = RoleRecord.objects.filter(name__iexact=name).first()
        return self._role(record) if record else None

    def save_role(self, role):
        RoleRecord.objects.update_or_create(
            id=role.id,
            defaults={
                "name": role.name,
                "permissions": sorted(role.permissions),
                "is_system": role.is_system,
                "created_at": role.created_at,
                "created_by": role.created_by,
                "updated_by": role.updated_by,
            },
        )

    def find_assignment(self, assignment_id):
        record = RoleAssignmentRecord.objects.filter(id=assignment_id).first()
        return self._assignment(record) if record else None

    def find_active_assignment(self, user_id, role_id, scope_id):
        query = RoleAssignmentRecord.objects.filter(
            user_id=user_id, role_id=role_id, revoked_at__isnull=True
        )
        query = query.filter(scope_type="global", scope_id__isnull=True) if scope_id is None else query.filter(
            scope_type="merchant", scope_id=scope_id
        )
        record = query.first()
        return self._assignment(record) if record else None

    def save_assignment(self, assignment):
        RoleAssignmentRecord.objects.update_or_create(
            id=assignment.id,
            defaults={
                "user_id": assignment.user_id,
                "role_id": assignment.role_id,
                "scope_type": assignment.scope_type,
                "scope_id": assignment.scope_id,
                "granted_by": assignment.granted_by,
                "granted_at": assignment.granted_at,
                "revoked_by": assignment.revoked_by,
                "revoked_at": assignment.revoked_at,
            },
        )

    def permissions_for(self, user_id, scope_type, scope_id):
        assignments = RoleAssignmentRecord.objects.filter(
            user_id=user_id, revoked_at__isnull=True
        )
        if scope_type == "merchant":
            assignments = assignments.filter(
                Q(scope_type="global") | Q(scope_type="merchant", scope_id=scope_id)
            )
        else:
            assignments = assignments.filter(scope_type="global")
        role_ids = assignments.values_list("role_id", flat=True)
        return frozenset(
            permission
            for permissions in RoleRecord.objects.filter(id__in=role_ids).values_list("permissions", flat=True)
            for permission in permissions
        )

    @staticmethod
    def _role(record):
        return Role(
            record.id, record.name, frozenset(record.permissions), record.is_system,
            record.created_at, record.created_by, record.updated_by,
        )

    @staticmethod
    def _assignment(record):
        return RoleAssignment(
            record.id, record.user_id, record.role_id, record.scope_type, record.scope_id,
            record.granted_by, record.granted_at, record.revoked_by, record.revoked_at,
        )
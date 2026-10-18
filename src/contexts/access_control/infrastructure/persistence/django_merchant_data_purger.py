"""Module: contexts/access_control/infrastructure/persistence/django_merchant_data_purger.py
Context: Access Control
Role: resumably delete merchant RoleAssignments while retaining identifier-only audit records.
"""

from django.db import transaction
from django.utils import timezone

from .models import (
    MerchantDeletionAuditRecord,
    MerchantDeletionProgressRecord,
    RoleAssignmentRecord,
)


class DjangoAccessControlMerchantPurger:
    """Purge each RoleAssignment separately and retain its audit identifiers (INV-AC-06, INV-TR-01)."""

    def purge_merchant_assignments(self, event_id, merchant_id) -> None:
        """Archive and delete each scoped assignment in a resumable transaction (INV-AC-06)."""
        assignment_ids = list(
            RoleAssignmentRecord.objects.filter(
                scope_type="merchant",
                scope_id=merchant_id,
            ).values_list("id", flat=True)
        )
        for assignment_id in assignment_ids:
            with transaction.atomic():
                if MerchantDeletionProgressRecord.objects.filter(
                    event_id=event_id,
                    assignment_id=assignment_id,
                ).exists():
                    continue
                assignment = RoleAssignmentRecord.objects.filter(
                    id=assignment_id,
                    scope_type="merchant",
                    scope_id=merchant_id,
                ).first()
                if assignment is not None:
                    MerchantDeletionAuditRecord.objects.update_or_create(
                        assignment_id=assignment.id,
                        defaults={
                            "user_id": assignment.user_id,
                            "role_id": assignment.role_id,
                            "scope_id": assignment.scope_id,
                            "granted_by": assignment.granted_by,
                            "granted_at": assignment.granted_at,
                            "revoked_by": assignment.revoked_by,
                            "revoked_at": assignment.revoked_at,
                            "purged_at": timezone.now(),
                        },
                    )
                    assignment.delete()
                MerchantDeletionProgressRecord.objects.create(
                    event_id=event_id,
                    merchant_id=merchant_id,
                    assignment_id=assignment_id,
                )
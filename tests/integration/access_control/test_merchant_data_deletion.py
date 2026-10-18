from datetime import datetime, timezone
from uuid import uuid4

from django.test import TestCase

from contexts.access_control.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase,
)
from contexts.access_control.infrastructure.messaging.merchant_data_deletion_handler import (
    handle_merchant_data_deleted,
)
from contexts.access_control.infrastructure.persistence.models import (
    MerchantDeletionAuditRecord,
    OutboxEventRecord,
    ProcessedEventRecord,
    RoleAssignmentRecord,
    RoleRecord,
)


class AccessControlMerchantDataDeletionTests(TestCase):
    def test_purge_removes_only_merchant_assignments_and_retains_audit(self):
        merchant_id = uuid4()
        other_merchant_id = uuid4()
        event_id = uuid4()
        role_id = uuid4()
        assigned_at = datetime(2026, 10, 18, tzinfo=timezone.utc)
        RoleRecord.objects.create(
            id=role_id,
            name="Owner",
            permissions=["merchant.delete_data"],
            is_system=True,
            created_at=assigned_at,
        )
        target = RoleAssignmentRecord.objects.create(
            user_id=uuid4(),
            role_id=role_id,
            scope_type="merchant",
            scope_id=merchant_id,
            granted_by="system",
            granted_at=assigned_at,
        )
        global_assignment = RoleAssignmentRecord.objects.create(
            user_id=uuid4(),
            role_id=role_id,
            scope_type="global",
            scope_id=None,
            granted_by="platform-admin",
            granted_at=assigned_at,
        )
        other_assignment = RoleAssignmentRecord.objects.create(
            user_id=uuid4(),
            role_id=role_id,
            scope_type="merchant",
            scope_id=other_merchant_id,
            granted_by="system",
            granted_at=assigned_at,
        )
        envelope = {
            "eventId": str(event_id),
            "eventType": "MerchantDataDeleted",
            "producedBy": "backup",
            "payload": {"merchant_id": str(merchant_id)},
        }

        handle_merchant_data_deleted(envelope)
        handle_merchant_data_deleted(envelope)

        self.assertFalse(RoleAssignmentRecord.objects.filter(id=target.id).exists())
        self.assertTrue(RoleAssignmentRecord.objects.filter(id=global_assignment.id).exists())
        self.assertTrue(RoleAssignmentRecord.objects.filter(id=other_assignment.id).exists())
        self.assertTrue(RoleRecord.objects.filter(id=role_id).exists())
        audit = MerchantDeletionAuditRecord.objects.get(assignment_id=target.id)
        self.assertEqual(audit.user_id, target.user_id)
        self.assertEqual(audit.role_id, role_id)
        self.assertEqual(
            ProcessedEventRecord.objects.filter(
                event_id=event_id,
                consumer_name=PurgeMerchantDataUseCase.CONSUMER_NAME,
            ).count(),
            1,
        )
        self.assertEqual(
            OutboxEventRecord.objects.filter(
                event_type="MerchantDataPurged",
                payload__context="access-control",
                payload__merchant_id=str(merchant_id),
            ).count(),
            1,
        )
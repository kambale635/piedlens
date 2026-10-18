import uuid

from django.db import models
from django.db.models import Q


class RoleRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    permissions = models.JSONField(default=list)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    created_by = models.CharField(max_length=64, default="system")
    updated_by = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "access_control_roles"


class RoleAssignmentRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    role_id = models.UUIDField(db_index=True)
    scope_type = models.CharField(max_length=16)
    scope_id = models.UUIDField(null=True, blank=True)
    granted_by = models.CharField(max_length=64)
    granted_at = models.DateTimeField()
    revoked_by = models.CharField(max_length=64, null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "access_control_role_assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "role_id", "scope_id"],
                condition=Q(revoked_at__isnull=True, scope_type="merchant"),
                name="uniq_active_merchant_role_assignment",
            ),
            models.UniqueConstraint(
                fields=["user_id", "role_id"],
                condition=Q(revoked_at__isnull=True, scope_type="global"),
                name="uniq_active_global_role_assignment",
            ),
        ]
        indexes = [models.Index(fields=["user_id", "scope_type", "scope_id", "revoked_at"])]


class ProcessedEventRecord(models.Model):
    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=160)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "access_control_processed_events"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "consumer_name"],
                name="uniq_access_control_processed_event",
            )
        ]


class MerchantDeletionAuditRecord(models.Model):
    assignment_id = models.UUIDField(primary_key=True)
    user_id = models.UUIDField()
    role_id = models.UUIDField()
    scope_id = models.UUIDField()
    granted_by = models.CharField(max_length=64)
    granted_at = models.DateTimeField()
    revoked_by = models.CharField(max_length=64, null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "access_control_merchant_deletion_audit"


class MerchantDeletionProgressRecord(models.Model):
    event_id = models.UUIDField()
    merchant_id = models.UUIDField()
    assignment_id = models.UUIDField()

    class Meta:
        db_table = "access_control_merchant_deletion_progress"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "assignment_id"],
                name="uniq_access_control_merchant_deletion_progress",
            )
        ]


class OutboxEventRecord(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="access_control")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "access_control_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]
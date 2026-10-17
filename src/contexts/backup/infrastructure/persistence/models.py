import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class BackupSnapshotRecord(models.Model):
    """Immutable persistence record for a BackupSnapshot aggregate (INV-BK-01/02)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField(db_index=True)
    platform_connection_id = models.UUIDField(db_index=True)
    snapshot_date = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=16)
    data_integrity_hash = models.CharField(max_length=64, blank=True)
    storage_reference = models.CharField(max_length=64, null=True, blank=True)
    message_count = models.PositiveIntegerField(default=0)
    media_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "backup_snapshots"
        indexes = [models.Index(fields=["merchant_id", "snapshot_date"])]


class BackupExportRecord(models.Model):
    """Merchant-scoped export job and expiring signed download metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField(db_index=True)
    platform_connection_id = models.UUIDField()
    status = models.CharField(max_length=16)
    storage_reference = models.CharField(max_length=64)
    download_url = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "backup_exports"
        indexes = [models.Index(fields=["merchant_id", "id"])]


class BackupObjectRecord(models.Model):
    """Local mock object store; replace with S3-compatible storage before production."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payload = models.JSONField(encoder=DjangoJSONEncoder)

    class Meta:
        db_table = "backup_objects"


class OutboxEventRecord(models.Model):
    """Durable Backup producer event committed with snapshot/deletion changes (INV-TR-02)."""

    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="backup")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(encoder=DjangoJSONEncoder)
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "backup_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]
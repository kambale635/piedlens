import uuid

from django.db import models


class PlatformConnectionRecord(models.Model):
    """Persistence record for the PlatformConnection aggregate (INV-PC-01)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField(db_index=True)
    platform_type = models.CharField(max_length=32)
    external_account_id = models.CharField(max_length=512)
    encrypted_access_token = models.TextField()
    status = models.CharField(max_length=16, db_index=True)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_connectors_connections"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant_id", "platform_type", "external_account_id"],
                name="uniq_platform_connection_account",
            )
        ]


class MessageRecord(models.Model):
    """Normalized inbound message record with a DB-enforced idempotency key (INV-PC-03)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform_connection_id = models.UUIDField()
    merchant_id = models.UUIDField(db_index=True)
    external_message_id = models.CharField(max_length=512)
    external_sender_id = models.CharField(max_length=512)
    display_name = models.CharField(max_length=512, blank=True)
    text_content = models.TextField(blank=True)
    received_at = models.DateTimeField()

    class Meta:
        db_table = "platform_connectors_messages"
        constraints = [
            models.UniqueConstraint(
                fields=["platform_connection_id", "external_message_id"],
                name="uniq_platform_external_message",
            )
        ]


class ProcessedEventRecord(models.Model):
    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=160)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_connectors_processed_events"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "consumer_name"],
                name="uniq_platform_connectors_processed_event",
            )
        ]


class MerchantDeletionProgressRecord(models.Model):
    event_id = models.UUIDField()
    merchant_id = models.UUIDField()
    aggregate_type = models.CharField(max_length=32)
    aggregate_id = models.UUIDField()

    class Meta:
        db_table = "platform_connectors_deletion_progress"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "aggregate_type", "aggregate_id"],
                name="uniq_platform_deletion_progress_item",
            )
        ]


class OutboxEventRecord(models.Model):
    """Durable event row committed with Platform Connectors writes (INV-TR-02)."""

    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="platform-connectors")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_connectors_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]
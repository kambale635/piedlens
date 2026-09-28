import uuid

from django.db import models


class ContactRecord(models.Model):
    """Django persistence record for the CRM Contact aggregate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField()
    platform_connection_id = models.UUIDField()
    external_identifier = models.CharField(max_length=512)
    display_name = models.CharField(max_length=512, blank=True)
    total_spent_by_currency = models.JSONField(default=dict)
    order_count = models.PositiveIntegerField(default=0)
    last_interaction_at = models.DateTimeField()
    purchase_history = models.JSONField(default=list)
    loyalty_score = models.PositiveSmallIntegerField(default=0)
    tags = models.JSONField(default=list)
    status = models.CharField(max_length=16, default="active")
    merged_into_contact_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "crm_contacts"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant_id", "platform_connection_id", "external_identifier"],
                name="uniq_crm_contact_platform_identity",
            )
        ]
        indexes = [models.Index(fields=["merchant_id", "last_interaction_at"])]


class ProcessedMessageRecord(models.Model):
    """CRM consumer idempotency marker committed with its Contact update."""

    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=160)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crm_processed_events"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "consumer_name"],
                name="uniq_crm_processed_event_consumer",
            )
        ]


class OutboxEventRecord(models.Model):
    """Durable CRM event committed atomically with its business write (INV-TR-02)."""

    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="crm")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "crm_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]


class RelationshipAnomalyNotificationRecord(models.Model):
    """CRM notification ledger enforcing one alert per purchase-silence period."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField()
    contact_id = models.UUIDField()
    last_purchase_order_id = models.UUIDField()
    days_since_last_purchase = models.FloatField()
    usual_interval_days = models.FloatField()
    notified_at = models.DateTimeField()

    class Meta:
        db_table = "crm_relationship_anomaly_notifications"
        constraints = [
            models.UniqueConstraint(
                fields=["contact_id", "last_purchase_order_id"],
                name="uniq_crm_anomaly_contact_silence",
            )
        ]
        indexes = [
            models.Index(
                fields=["merchant_id", "notified_at"],
                name="crm_rel_anomaly_merchant_idx",
            )
        ]
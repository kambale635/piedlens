import uuid

from django.db import models


class OrderRecord(models.Model):
    """Django persistence record for the Order Detection aggregate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField()
    contact_id = models.UUIDField()
    source_candidate_id = models.UUIDField(null=True, blank=True, unique=True)
    detected_amount = models.DecimalField(max_digits=20, decimal_places=4)
    currency = models.CharField(max_length=3)
    confidence_score = models.PositiveSmallIntegerField()
    source_message_ids = models.JSONField(default=list)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField()
    last_status_change_at = models.DateTimeField()
    latest_amount_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "order_detection_orders"
        indexes = [
            models.Index(fields=["contact_id", "status", "created_at"]),
            models.Index(fields=["merchant_id", "status", "created_at"]),
        ]


class DetectionCandidateRecord(models.Model):
    """Django persistence record for one low-confidence candidate aggregate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField(db_index=True)
    contact_id = models.UUIDField()
    detected_amount = models.DecimalField(max_digits=20, decimal_places=4)
    currency = models.CharField(max_length=3)
    confidence_score = models.PositiveSmallIntegerField()
    source_message_id = models.UUIDField()
    matched_rule_ids = models.JSONField(default=list)
    status = models.CharField(max_length=32, db_index=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "order_detection_candidates"
        indexes = [models.Index(fields=["merchant_id", "status", "created_at"])]


class OutboxEventRecord(models.Model):
    """Durable producer event written atomically with its aggregate change."""

    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="order-detection")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "order_detection_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]


class ProcessedEventRecord(models.Model):
    """Consumer idempotency marker committed with the consumer's aggregate work."""

    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=160)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_detection_processed_events"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "consumer_name"],
                name="uniq_order_detection_processed_event_consumer",
            )
        ]


class CandidateOrderCreationLockRecord(models.Model):
    """Stable row used to serialize concurrent Order creation for one candidate."""

    candidate_id = models.UUIDField(primary_key=True)

    class Meta:
        db_table = "order_detection_candidate_order_locks"


class ReminderRecord(models.Model):
    """Persistence record for the Reminder aggregate and deferred scheduler payload."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.UUIDField(db_index=True)
    reminder_type = models.CharField(max_length=32)
    status = models.CharField(max_length=32)
    scheduled_for = models.DateTimeField(db_index=True)
    custom_message = models.TextField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    lease_until = models.DateTimeField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "order_detection_reminders"
        constraints = [
            models.UniqueConstraint(
                fields=["order_id", "reminder_type"],
                condition=models.Q(status__in=["scheduled", "processing"]),
                name="uniq_scheduled_reminder_order_type",
            )
        ]
        indexes = [models.Index(fields=["status", "scheduled_for"])]
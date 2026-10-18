import uuid

from django.db import models


class RuleSetRecord(models.Model):
    """Rules Engine-owned RuleSet aggregate persistence record (INV-RE-01)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=96, unique=True)
    version = models.PositiveIntegerField(default=1)
    rules = models.JSONField(default=list)

    class Meta:
        db_table = "rules_engine_rule_sets"


class ProcessedEventRecord(models.Model):
    """Idempotency ledger for Rules Engine event consumers (INV-TR-03)."""

    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=160)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rules_engine_processed_events"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "consumer_name"],
                name="uniq_rules_engine_processed_event",
            )
        ]


class MerchantDeletionProgressRecord(models.Model):
    event_id = models.UUIDField()
    merchant_id = models.UUIDField()
    rule_set_id = models.UUIDField()

    class Meta:
        db_table = "rules_engine_deletion_progress"
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "rule_set_id"],
                name="uniq_rules_engine_deletion_progress",
            )
        ]


class OutboxEventRecord(models.Model):
    """Durable producer event row committed with Rules Engine writes (INV-TR-02)."""

    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="rules-engine")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "rules_engine_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]
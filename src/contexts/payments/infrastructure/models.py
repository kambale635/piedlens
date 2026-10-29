import uuid

from django.db import models
from django.db.models import Q


class PaymentRouteRecord(models.Model):
    country = models.CharField(max_length=2)
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=24)
    provider_code = models.CharField(max_length=64)
    priority = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)
    supports_escrow = models.BooleanField(default=False)
    config = models.JSONField(default=dict)

    class Meta:
        db_table = "payments_routes"
        constraints = [models.UniqueConstraint(fields=["country", "currency", "method", "provider_code"], name="uniq_payment_route")]
        indexes = [models.Index(fields=["country", "currency", "method", "active", "priority"])]


class PaymentAttemptRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField(db_index=True)
    payable_type = models.CharField(max_length=32)
    payable_id = models.UUIDField(db_index=True)
    payable_reference = models.CharField(max_length=64, blank=True)
    provider_code = models.CharField(max_length=64)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    fee_minor = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=32, db_index=True)
    proof_status = models.CharField(max_length=32, default="unverified")
    provider_reference = models.CharField(max_length=160, null=True, blank=True)
    idempotency_key = models.CharField(max_length=160)
    request_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "payments_attempts"
        constraints = [
            models.UniqueConstraint(fields=["merchant_id", "idempotency_key"], name="uniq_payment_idempotency"),
            models.UniqueConstraint(fields=["merchant_id", "payable_type", "payable_id"], condition=Q(status="succeeded"), name="uniq_successful_payment_per_payable"),
        ]
        indexes = [models.Index(fields=["merchant_id", "status", "created_at"])]


class PaymentProviderEventRecord(models.Model):
    provider_code = models.CharField(max_length=64)
    provider_event_id = models.CharField(max_length=160)
    payload_hash = models.CharField(max_length=64)
    processed_at = models.DateTimeField(null=True, blank=True)
    payment_attempt_id = models.UUIDField(db_index=True)

    class Meta:
        db_table = "payments_provider_events"
        constraints = [models.UniqueConstraint(fields=["provider_code", "provider_event_id"], name="uniq_provider_event_id")]


class PaymentEventRecord(models.Model):
    event_id = models.UUIDField(primary_key=True)
    payment_attempt_id = models.UUIDField(db_index=True)
    merchant_id = models.UUIDField(db_index=True)
    event_type = models.CharField(max_length=40)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    occurred_at = models.DateTimeField()
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "payments_payment_events"
        indexes = [models.Index(fields=["merchant_id", "occurred_at"])]


class SettlementAccountRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_id = models.UUIDField(db_index=True)
    method = models.CharField(max_length=24)
    network_code = models.CharField(max_length=64, blank=True)
    account_reference_encrypted = models.TextField()
    verified_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "payments_settlement_accounts"


class OutboxEventRecord(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    occurred_at = models.DateTimeField()
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]


class ProcessedEventRecord(models.Model):
    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=160)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments_processed_events"
        constraints = [models.UniqueConstraint(fields=["event_id", "consumer_name"], name="uniq_payments_processed_event")]

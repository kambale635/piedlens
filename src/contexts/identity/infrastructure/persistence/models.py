import uuid

from django.db import models


class UserRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=16, unique=True)
    email = models.EmailField(null=True, blank=True)
    password_hash = models.CharField(max_length=256)
    status = models.CharField(max_length=16, default="active")
    created_at = models.DateTimeField()

    class Meta:
        db_table = "identity_users"


class MerchantRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=2)
    preferred_language = models.CharField(max_length=2)
    currency = models.CharField(max_length=3)
    subscription_plan = models.CharField(max_length=16, default="starter")
    created_at = models.DateTimeField()

    class Meta:
        db_table = "identity_merchants"


class OutboxEventRecord(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField()
    produced_by = models.CharField(max_length=80, default="identity")
    correlation_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "identity_outbox_events"
        indexes = [models.Index(fields=["published_at", "occurred_at"])]
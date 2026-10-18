import uuid

from django.db import models


class AppendOnlyAuditLogQuerySet(models.QuerySet):
    """Reject mutation APIs while allowing audit rows to be queried normally."""

    def update(self, **kwargs):
        raise ValueError("Audit log records are append-only.")

    def delete(self):
        raise ValueError("Audit log records are append-only.")


class AppendOnlyAuditLogManager(models.Manager):
    use_in_migrations = True

    def get_queryset(self):
        return AppendOnlyAuditLogQuerySet(self.model, using=self._db)


class AuditLogRecord(models.Model):
    """Append-only request audit metadata; bodies, payment data and tokens are excluded."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    correlation_id = models.CharField(max_length=128, blank=True)
    user_id = models.CharField(max_length=64, blank=True)
    merchant_id = models.CharField(max_length=64, blank=True)
    permission = models.CharField(max_length=160, null=True, blank=True)
    outcome = models.CharField(max_length=32)
    route = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AppendOnlyAuditLogManager()

    class Meta:
        db_table = "event_bus_audit_log"
        indexes = [models.Index(fields=["merchant_id", "created_at"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Audit log records are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit log records are append-only.")
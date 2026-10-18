"""Module: contexts/backup/infrastructure/persistence/s3_object_deletion_worker.py
Context: Backup
Role: deliver durable S3 deletion jobs after the database transaction has committed.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import S3ObjectDeletionRecord


class S3ObjectDeletionWorker:
    """Retry remote object deletions without coupling S3 availability to Backup transactions (INV-BK-06)."""

    def __init__(self, storage, batch_size: int, backoff_base_seconds: float, backoff_max_seconds: float):
        self._storage = storage
        self._batch_size = batch_size
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_max_seconds = backoff_max_seconds

    def process_once(self) -> tuple[int, int]:
        """Attempt one due batch and retain failed jobs with bounded exponential retry."""
        due_ids = list(
            S3ObjectDeletionRecord.objects.filter(next_attempt_at__lte=timezone.now())
            .order_by("next_attempt_at", "id")
            .values_list("id", flat=True)[: self._batch_size]
        )
        deleted = 0
        failed = 0
        for record_id in due_ids:
            with transaction.atomic():
                record = (
                    S3ObjectDeletionRecord.objects.select_for_update()
                    .filter(id=record_id, next_attempt_at__lte=timezone.now())
                    .first()
                )
                if record is None:
                    continue
                reference = record.reference
                record.attempts += 1
                delay = min(
                    self._backoff_base_seconds * (2 ** (record.attempts - 1)),
                    self._backoff_max_seconds,
                )
                record.next_attempt_at = timezone.now() + timedelta(seconds=delay)
                record.save(update_fields=["attempts", "next_attempt_at"])
            try:
                self._storage.delete_now(reference)
            except Exception as error:
                S3ObjectDeletionRecord.objects.filter(id=record_id).update(
                    last_error_type=type(error).__name__
                )
                failed += 1
            else:
                S3ObjectDeletionRecord.objects.filter(id=record_id).delete()
                deleted += 1
        return deleted, failed
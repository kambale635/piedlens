import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from contexts.backup.infrastructure.persistence.s3_object_storage import S3ObjectStorage
from contexts.backup.infrastructure.persistence.s3_object_deletion_worker import (
    S3ObjectDeletionWorker,
)


class Command(BaseCommand):
    help = "Retry queued S3 object deletions."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        if settings.BACKUP_OBJECT_STORAGE_BACKEND != "s3":
            raise CommandError("run_s3_deletion_worker requires BACKUP_OBJECT_STORAGE_BACKEND=s3.")
        worker = S3ObjectDeletionWorker(
            storage=S3ObjectStorage(),
            batch_size=settings.BACKUP_S3_DELETE_BATCH_SIZE,
            backoff_base_seconds=settings.BACKUP_S3_DELETE_BACKOFF_BASE_SECONDS,
            backoff_max_seconds=settings.BACKUP_S3_DELETE_BACKOFF_MAX_SECONDS,
        )
        while True:
            deleted, failed = worker.process_once()
            if deleted or failed:
                self.stdout.write(f"S3 deletion jobs completed={deleted} retrying={failed}")
            if options["once"]:
                return
            time.sleep(settings.OUTBOX_RELAY_POLL_INTERVAL_SECONDS)
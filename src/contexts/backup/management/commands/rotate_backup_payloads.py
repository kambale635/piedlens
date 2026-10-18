from django.core.management.base import BaseCommand

from contexts.backup.infrastructure.persistence.models import (
    BackupExportRecord,
    BackupObjectRecord,
    BackupSnapshotRecord,
)
from contexts.backup.infrastructure.persistence.s3_object_storage import (
    configured_object_storage,
)
from contexts.backup.infrastructure.persistence.django_object_storage import DjangoObjectStorage


class Command(BaseCommand):
    """Rotate every stored Backup object to its configured active key version."""

    help = "Re-encrypt stored Backup payloads with the active key version."

    def handle(self, *args, **options):
        """Rotate objects independently and report only the number changed."""
        storage = configured_object_storage()
        if isinstance(storage, DjangoObjectStorage):
            references = BackupObjectRecord.objects.order_by("id").values_list("id", flat=True)
        else:
            snapshot_references = BackupSnapshotRecord.objects.exclude(
                storage_reference__isnull=True
            ).values_list("storage_reference", flat=True)
            export_references = BackupExportRecord.objects.values_list(
                "storage_reference", flat=True
            )
            references = set(snapshot_references).union(export_references)

        rotated_count = sum(storage.rotate_object(str(reference)) for reference in references)
        self.stdout.write(f"Rotated {rotated_count} backup object(s).")
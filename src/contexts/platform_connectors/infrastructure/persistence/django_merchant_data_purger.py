"""Module: contexts/platform_connectors/infrastructure/persistence/django_merchant_data_purger.py
Context: Platform Connectors
Role: delete connection credentials and merchant messages one record per resumable transaction.
"""

from django.db import transaction

from .models import (
    MerchantDeletionProgressRecord,
    MessageRecord,
    PlatformConnectionRecord,
)


class DjangoPlatformConnectorsMerchantPurger:
    """Remove each connection and message separately, recording restart progress (INV-PC-05, INV-TR-01)."""

    def purge_merchant_data(self, event_id, merchant_id) -> None:
        """Delete connections first, then messages, with each write checkpointed atomically (INV-PC-05)."""
        connection_ids = list(
            PlatformConnectionRecord.objects.filter(merchant_id=merchant_id)
            .order_by("id")
            .values_list("id", flat=True)
        )
        for connection_id in connection_ids:
            self._delete_record(event_id, merchant_id, "connection", connection_id)

        message_ids = list(
            MessageRecord.objects.filter(merchant_id=merchant_id)
            .order_by("id")
            .values_list("id", flat=True)
        )
        for message_id in message_ids:
            self._delete_record(event_id, merchant_id, "message", message_id)

    @staticmethod
    def _delete_record(event_id, merchant_id, aggregate_type, aggregate_id) -> None:
        with transaction.atomic():
            progress = MerchantDeletionProgressRecord.objects.filter(
                event_id=event_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            ).exists()
            if progress:
                return
            model = PlatformConnectionRecord if aggregate_type == "connection" else MessageRecord
            model.objects.filter(id=aggregate_id, merchant_id=merchant_id).delete()
            MerchantDeletionProgressRecord.objects.create(
                event_id=event_id,
                merchant_id=merchant_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            )
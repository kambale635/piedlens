"""Module: contexts/crm/infrastructure/persistence/django_merchant_data_purger.py
Context: CRM
Role: delete merchant-owned CRM aggregates and child delivery journals with restart progress.
"""

from django.db import transaction

from .models import (
    BulkMessageCampaignRecord,
    BulkMessageRecipientRecord,
    ContactRecord,
    MerchantDeletionProgressRecord,
    RelationshipAnomalyNotificationRecord,
    SegmentRecord,
)


class DjangoCRMMerchantPurger:
    """Delete each CRM aggregate and recipient journal separately (INV-CRM-09, INV-TR-01)."""

    def purge_merchant_data(self, event_id, merchant_id) -> None:
        """Delete local contacts, segments, notifications, recipient journals and campaigns with checkpoints."""
        self._purge_owned_records(
            event_id, merchant_id, "contact", ContactRecord.objects.filter(merchant_id=merchant_id), ContactRecord
        )
        self._purge_owned_records(
            event_id, merchant_id, "segment", SegmentRecord.objects.filter(merchant_id=merchant_id), SegmentRecord
        )
        self._purge_owned_records(
            event_id,
            merchant_id,
            "anomaly_notification",
            RelationshipAnomalyNotificationRecord.objects.filter(merchant_id=merchant_id),
            RelationshipAnomalyNotificationRecord,
        )

        campaign_ids = list(
            BulkMessageCampaignRecord.objects.filter(merchant_id=merchant_id)
            .order_by("id")
            .values_list("id", flat=True)
        )
        for campaign_id in campaign_ids:
            recipient_ids = list(
                BulkMessageRecipientRecord.objects.filter(campaign_id=campaign_id)
                .order_by("id")
                .values_list("id", flat=True)
            )
            for recipient_id in recipient_ids:
                self._delete(
                    event_id,
                    merchant_id,
                    "campaign_recipient",
                    recipient_id,
                    BulkMessageRecipientRecord,
                    {"id": recipient_id, "campaign_id": campaign_id},
                )
        self._purge_owned_records(
            event_id,
            merchant_id,
            "campaign",
            BulkMessageCampaignRecord.objects.filter(merchant_id=merchant_id),
            BulkMessageCampaignRecord,
        )

    def _purge_owned_records(self, event_id, merchant_id, aggregate_type, queryset, model) -> None:
        for aggregate_id in queryset.order_by("id").values_list("id", flat=True):
            self._delete(
                event_id,
                merchant_id,
                aggregate_type,
                aggregate_id,
                model,
                {"id": aggregate_id, "merchant_id": merchant_id},
            )

    @staticmethod
    def _delete(event_id, merchant_id, aggregate_type, aggregate_id, model, filters) -> None:
        with transaction.atomic():
            if MerchantDeletionProgressRecord.objects.filter(
                event_id=event_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            ).exists():
                return
            model.objects.filter(**filters).delete()
            MerchantDeletionProgressRecord.objects.create(
                event_id=event_id,
                merchant_id=merchant_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            )
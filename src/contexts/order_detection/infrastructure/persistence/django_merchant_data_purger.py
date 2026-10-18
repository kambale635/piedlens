"""Module: contexts/order_detection/infrastructure/persistence/django_merchant_data_purger.py
Context: Order Detection
Role: purge local merchant aggregates one at a time with durable progress markers.
"""

from django.db import transaction

from .models import (
    ContactReferenceRedirectRecord,
    DetectionCandidateRecord,
    MerchantDeletionProgressRecord,
    OrderRecord,
    ReminderRecord,
)


class DjangoOrderDetectionMerchantPurger:
    """Delete each local merchant aggregate in a separate resumable transaction (INV-OD-08, INV-TR-01)."""

    def purge_merchant_data(self, event_id, merchant_id) -> None:
        """Purge orders, reminders, candidates and local redirects without cross-context access."""
        order_ids = list(
            OrderRecord.objects.filter(merchant_id=merchant_id)
            .order_by("id")
            .values_list("id", flat=True)
        )
        reminder_items = [
            (order_id, reminder_id)
            for order_id in order_ids
            for reminder_id in ReminderRecord.objects.filter(order_id=order_id)
            .order_by("id")
            .values_list("id", flat=True)
        ]
        for order_id in order_ids:
            self._delete(
                event_id,
                merchant_id,
                "order",
                order_id,
                OrderRecord,
                {"id": order_id, "merchant_id": merchant_id},
            )
        for order_id, reminder_id in reminder_items:
            self._delete(
                event_id,
                merchant_id,
                "reminder",
                reminder_id,
                ReminderRecord,
                {"id": reminder_id, "order_id": order_id},
            )

        candidate_ids = list(
            DetectionCandidateRecord.objects.filter(merchant_id=merchant_id)
            .order_by("id")
            .values_list("id", flat=True)
        )
        for candidate_id in candidate_ids:
            self._delete(
                event_id,
                merchant_id,
                "candidate",
                candidate_id,
                DetectionCandidateRecord,
                {"id": candidate_id, "merchant_id": merchant_id},
            )

        redirect_ids = list(
            ContactReferenceRedirectRecord.objects.filter(merchant_id=merchant_id)
            .order_by("merged_contact_id")
            .values_list("merged_contact_id", flat=True)
        )
        for redirect_id in redirect_ids:
            self._delete(
                event_id,
                merchant_id,
                "contact_redirect",
                redirect_id,
                ContactReferenceRedirectRecord,
                {"merged_contact_id": redirect_id, "merchant_id": merchant_id},
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
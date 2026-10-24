"""Module: contexts/order_detection/infrastructure/django_order_repository.py
Context: Order Detection.
Role: map the Order aggregate to its PostgreSQL persistence record.
"""

from decimal import Decimal
from uuid import UUID

from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money

from ...domain.entities.order import Order
from ...domain.value_objects.order_status import OrderStatus
from .models import OrderRecord


class DjangoOrderRepository:
    """Persist Order aggregates without leaking Django ORM into the domain."""

    def save(self, order: Order) -> None:
        """Insert/update an aggregate; database uniqueness enforces candidate idempotency."""
        OrderRecord.objects.update_or_create(
            id=order.id,
            defaults={
                "merchant_id": order.merchant_id,
                "contact_id": order.contact_id,
                "source_candidate_id": order.source_candidate_id,
                "detected_amount": order.detected_amount.amount,
                "currency": order.detected_amount.currency,
                "confidence_score": order.confidence_score.value,
                "source_message_ids": [str(value) for value in order.source_message_ids],
                "status": order.status.value,
                "created_at": order.created_at,
                "last_status_change_at": order.last_status_change_at,
                "latest_amount_at": order.latest_amount_at,
            },
        )

    def find_by_id(self, order_id: UUID) -> Order | None:
        """Load an Order aggregate by its public identifier."""
        record = OrderRecord.objects.filter(id=order_id).first()
        return self._to_domain(record) if record else None

    def find_for_update_by_id(self, order_id: UUID) -> Order | None:
        """Lock and rehydrate one Order for an isolated aggregate transaction."""
        record = OrderRecord.objects.select_for_update().filter(id=order_id).first()
        return self._to_domain(record) if record else None

    def find_ids_by_contact(self, contact_id: UUID) -> list[UUID]:
        """Return stable Order IDs still pointing at the specified Contact."""
        return list(
            OrderRecord.objects.filter(contact_id=contact_id)
            .order_by("id")
            .values_list("id", flat=True)
        )

    def find_by_source_candidate_id(self, candidate_id: UUID) -> Order | None:
        """Return the Order created for a candidate, if the unique key exists."""
        record = OrderRecord.objects.filter(source_candidate_id=candidate_id).first()
        return self._to_domain(record) if record else None

    def find_pending_by_contact(self, contact_id: UUID, within_days: int) -> list[Order]:
        """Return open Orders for a contact in the configured recent window."""
        from datetime import timedelta
        from django.utils import timezone

        threshold = timezone.now() - timedelta(days=within_days)
        records = OrderRecord.objects.select_for_update().filter(
            contact_id=contact_id,
            status__in=[OrderStatus.PENDING_PAYMENT.value, OrderStatus.PAID_NOT_DELIVERED.value],
            created_at__gte=threshold,
        ).order_by("-created_at")
        return [self._to_domain(record) for record in records]

    def find_orders_for_status_reconciliation(
        self,
        merchant_id: UUID,
        contact_id: UUID,
        expected_status: str,
        source_timestamp,
        within_days: int,
    ) -> list[Order]:
        """Lock matching Orders in the configured window ending at source time (INV-OD-09)."""
        from datetime import timedelta

        records = OrderRecord.objects.select_for_update().filter(
            merchant_id=merchant_id,
            contact_id=contact_id,
            status=expected_status,
            created_at__gte=source_timestamp - timedelta(days=within_days),
            created_at__lte=source_timestamp,
        ).order_by("-created_at", "-id")
        return [self._to_domain(record) for record in records]

    def find_dormant(self, merchant_id: UUID, older_than_hours: int) -> list[Order]:
        """Read old open Orders for one merchant in dashboard display order."""
        from datetime import timedelta
        from django.utils import timezone

        threshold = timezone.now() - timedelta(hours=older_than_hours)
        records = OrderRecord.objects.filter(
            merchant_id=merchant_id,
            status__in=[OrderStatus.PENDING_PAYMENT.value, OrderStatus.PAID_NOT_DELIVERED.value],
            created_at__lt=threshold,
        ).order_by("created_at", "-detected_amount")
        return [self._to_domain(record) for record in records]

    @staticmethod
    def _to_domain(record: OrderRecord) -> Order:
        """Rehydrate an Order while preserving its protected aggregate state."""
        order = Order(
            id=record.id,
            merchant_id=record.merchant_id,
            contact_id=record.contact_id,
            source_candidate_id=record.source_candidate_id,
            _detected_amount=Money(Decimal(record.detected_amount), record.currency),
            confidence_score=ConfidenceScore(record.confidence_score),
            _source_message_ids=[UUID(value) for value in record.source_message_ids],
            _status=OrderStatus(record.status),
            _created_at=record.created_at,
            _last_status_change_at=record.last_status_change_at,
            _recorded_amount_message_ids={UUID(value) for value in record.source_message_ids},
            _latest_amount_at=record.latest_amount_at,
        )
        return order
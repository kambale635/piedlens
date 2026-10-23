from collections import defaultdict
from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from django.db.models import Sum

from shared_kernel.ports import IOrderValueReportReader

from ..persistence.models import OrderRecord, OutboxEventRecord


class DjangoOrderValueReportReader(IOrderValueReportReader):
    """Read Order Detection-owned pending amounts and recorded payment transitions."""

    def monthly_order_amounts(self, merchant_id: UUID, month) -> dict[str, list[dict]]:
        start = datetime.combine(month, time.min, tzinfo=timezone.utc)
        next_month = month.replace(day=28) + __import__("datetime").timedelta(days=4)
        next_month = next_month.replace(day=1)
        end = datetime.combine(next_month, time.min, tzinfo=timezone.utc)

        pending_rows = (
            OrderRecord.objects.filter(
                merchant_id=merchant_id,
                status="pending_payment",
                created_at__gte=start,
                created_at__lt=end,
            )
            .values("currency")
            .annotate(amount=Sum("detected_amount"))
        )
        pending = [
            {"currency": row["currency"], "amount": str(row["amount"] or 0)}
            for row in pending_rows
        ]

        recovered_by_currency: dict[str, Decimal] = defaultdict(Decimal)
        paid_events = OutboxEventRecord.objects.filter(
            event_type="OrderStatusChanged",
            payload__merchant_id=str(merchant_id),
            payload__previous_status="pending_payment",
            payload__status__in=["paid_not_delivered", "paid_and_delivered"],
        )
        seen_order_ids: set[str] = set()
        for event in paid_events.iterator():
            payload = event.payload
            updated_at = payload.get("updated_at")
            if not updated_at:
                continue
            try:
                paid_at = datetime.fromisoformat(updated_at)
            except (TypeError, ValueError):
                continue
            if paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=timezone.utc)
            if not start <= paid_at < end:
                continue
            order_id = str(payload.get("order_id", ""))
            if not order_id or order_id in seen_order_ids:
                continue
            amount = payload.get("detected_amount") or {}
            currency = amount.get("currency")
            raw_amount = amount.get("amount")
            if not currency or raw_amount is None:
                continue
            seen_order_ids.add(order_id)
            recovered_by_currency[currency] += Decimal(str(raw_amount))

        recovered = [
            {"currency": currency, "amount": str(amount)}
            for currency, amount in sorted(recovered_by_currency.items())
        ]
        return {
            "amounts_to_follow_up": pending,
            "amounts_recovered": recovered,
        }
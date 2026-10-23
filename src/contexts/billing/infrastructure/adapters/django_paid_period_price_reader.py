from datetime import datetime, time, timezone
from uuid import UUID

from ..persistence.models import PaidPeriodRecord


class DjangoPaidPeriodPriceReader:
    """Expose only actual payment snapshots for one merchant and calendar month."""

    def actual_paid_price(self, merchant_id: UUID, month):
        start = datetime.combine(month, time.min, tzinfo=timezone.utc)
        if month.month == 12:
            end = datetime.combine(month.replace(year=month.year + 1, month=1), time.min, tzinfo=timezone.utc)
        else:
            end = datetime.combine(month.replace(month=month.month + 1), time.min, tzinfo=timezone.utc)
        record = PaidPeriodRecord.objects.filter(
            merchant_id=merchant_id, paid_at__gte=start, paid_at__lt=end
        ).first()
        if record is None or record.amount_minor is None or not record.currency:
            return None
        return {"amountMinor": record.amount_minor, "currency": record.currency}
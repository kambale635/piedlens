from datetime import date

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from shared_kernel.application_exceptions import OutboundQuotaExceededException
from shared_kernel.ports import IOutboundCostEstimator, IOutboundUsageRecorder

from ..persistence.models import (
    BillingMerchantLockRecord,
    OutboundMessageUsageRecord,
    OutboundRateRecord,
)


class DjangoOutboundCostEstimator(IOutboundCostEstimator):
    """Read the currently effective country/category fee without currency conversion."""

    def estimate(self, country, currency, category, count):
        now = timezone.now()
        rate = OutboundRateRecord.objects.filter(
            country=country.upper(),
            currency=currency.upper(),
            category=category,
            is_active=True,
            valid_from__lte=now,
        ).filter(
            models_valid_until(now)
        ).order_by("-valid_from").first()
        if rate is None:
            return None
        return {
            "unitAmountMinor": rate.amount_minor,
            "amountMinor": rate.amount_minor * count,
            "currency": rate.currency,
            "numberOfMessages": count,
            "chargeProcessor": "meta_direct",
        }


class DjangoMerchantOutboundUsageReader:
    """Expose current-month outbound counts through a tenant-scoped application read port."""

    def usage_for(self, merchant_id):
        now = timezone.now()
        month = date(now.year, now.month, 1)
        return list(
            OutboundMessageUsageRecord.objects.filter(
                merchant_id=merchant_id, month=month
            ).order_by("category").values("month", "category", "count")
        )


class DjangoOutboundUsageRecorder(IOutboundUsageRecorder):
    """Meter API messages against entitlements in a Billing-owned transaction."""

    def __init__(self, entitlements):
        self._entitlements = entitlements

    def reserve(self, merchant_id, category, idempotency_key):
        now = timezone.now()
        month = date(now.year, now.month, 1)
        with transaction.atomic():
            BillingMerchantLockRecord.objects.get_or_create(merchant_id=merchant_id)
            BillingMerchantLockRecord.objects.select_for_update().get(
                merchant_id=merchant_id
            )
            from ..persistence.models import OutboundMessageReservationRecord

            reservation, created = OutboundMessageReservationRecord.objects.get_or_create(
                idempotency_key=idempotency_key,
                defaults={
                    "merchant_id": merchant_id,
                    "month": month,
                    "category": category,
                },
            )
            if not created:
                if reservation.merchant_id != merchant_id:
                    raise OutboundQuotaExceededException()
                usage = OutboundMessageUsageRecord.objects.get(
                    merchant_id=merchant_id,
                    month=reservation.month,
                    category=reservation.category,
                )
                return {"month": reservation.month.isoformat(), "category": reservation.category, "count": usage.count}
            usage, _ = OutboundMessageUsageRecord.objects.select_for_update().get_or_create(
                merchant_id=merchant_id,
                month=month,
                category=category,
                defaults={"count": 0},
            )
            total_usage = OutboundMessageUsageRecord.objects.filter(
                merchant_id=merchant_id, month=month
            ).aggregate(total=Sum("count"))["total"] or 0
            cap = self._entitlements.entitlements_for(merchant_id).get(
                "outbound_monthly_cap", 0
            )
            if not isinstance(cap, int) or isinstance(cap, bool) or cap < -1:
                raise OutboundQuotaExceededException()
            if cap != -1 and total_usage + 1 > cap:
                raise OutboundQuotaExceededException()
            usage.count += 1
            usage.save(update_fields=["count"])
        return {"month": month.isoformat(), "category": category, "count": usage.count}

    def usage_for(self, merchant_id):
        return DjangoMerchantOutboundUsageReader().usage_for(merchant_id)


def models_valid_until(now):
    from django.db.models import Q

    return Q(valid_until__isnull=True) | Q(valid_until__gt=now)
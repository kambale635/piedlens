from django.db import transaction

from ...application.ports.plan_admin_repository import (
    IPlanAdminRepository,
    PlanAdminRecord,
    PlanPriceAdminRecord,
)
from .models import PlanDefinitionRecord, PlanEntitlementRecord, PlanPriceRecord


class DjangoPlanAdminRepository(IPlanAdminRepository):
    """Persist admin plan changes atomically in Billing-owned tables."""

    @transaction.atomic
    def upsert_plan(self, code, is_active, display_order, entitlements):
        plan, _ = PlanDefinitionRecord.objects.update_or_create(
            code=code,
            defaults={"is_active": is_active, "display_order": display_order},
        )
        for key, value in entitlements.items():
            PlanEntitlementRecord.objects.update_or_create(
                plan=plan, key=key, defaults={"value": value}
            )
        return PlanAdminRecord(plan.code, plan.is_active, plan.display_order)

    def upsert_price(
        self, plan_code, country, currency, period_days, amount_minor, is_active
    ):
        plan = PlanDefinitionRecord.objects.filter(code=plan_code).first()
        if plan is None:
            return None
        price, _ = PlanPriceRecord.objects.update_or_create(
            plan=plan,
            country=country,
            currency=currency,
            period_days=period_days,
            defaults={"amount_minor": amount_minor, "is_active": is_active},
        )
        return PlanPriceAdminRecord(
            plan.code,
            price.country,
            price.currency,
            price.period_days,
            price.amount_minor,
            price.is_active,
        )
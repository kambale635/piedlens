from ..persistence.models import PlanDefinitionRecord, PlanPriceRecord


class DjangoPlanPricingReader:
    """Read active Billing prices with an exact-country-first fallback."""

    def pricing_for_country(self, country: str) -> list[dict[str, object]]:
        plans = []
        active_plans = PlanDefinitionRecord.objects.filter(is_active=True).order_by(
            "display_order", "code"
        )
        for plan in active_plans:
            exact_prices = list(
                PlanPriceRecord.objects.filter(
                    plan=plan, country=country, is_active=True
                ).order_by("currency", "period_days")
            )
            fallback_prices = list(
                PlanPriceRecord.objects.filter(
                    plan=plan, country="*", is_active=True
                ).order_by("currency", "period_days")
            )
            exact_keys = {(price.currency, price.period_days) for price in exact_prices}
            prices = exact_prices + [
                price
                for price in fallback_prices
                if (price.currency, price.period_days) not in exact_keys
            ]
            plans.append(
                {
                    "code": plan.code,
                    "prices": [
                        {
                            "country": price.country,
                            "currency": price.currency,
                            "periodDays": price.period_days,
                            "amountMinor": price.amount_minor,
                        }
                        for price in prices
                    ],
                    "entitlements": dict(
                        plan.entitlements.values_list("key", "value")
                    ),
                }
            )
        return plans

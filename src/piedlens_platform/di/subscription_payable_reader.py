from contexts.billing.infrastructure.persistence.models import PlanPriceRecord


class SubscriptionPayableReader:
    """Compose Identity and Billing readers at the system boundary (INV-PAY-01/05/T5)."""

    def __init__(self, country_reader, currency_reader):
        self._country_reader = country_reader
        self._currency_reader = currency_reader

    def subscription_price(self, merchant_id, plan_code, period_days):
        country = self._country_reader.country_code_for(merchant_id)
        currency = self._currency_reader.currency_for(merchant_id)
        price = PlanPriceRecord.objects.filter(
            plan__code=plan_code,
            plan__is_active=True,
            country=country,
            currency=currency,
            period_days=period_days,
            is_active=True,
        ).first()
        if price is None:
            return None
        return {"country": country, "currency": currency, "amount_minor": price.amount_minor}

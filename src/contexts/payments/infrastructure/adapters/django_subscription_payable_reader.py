from uuid import UUID

from ..repositories import DjangoPaymentPriceReader


class DjangoSubscriptionPayableReader:
    """Compute subscription payable from configured Billing catalog, never client amounts (INV-PAY-01/05/T5)."""

    def __init__(self, price_reader=None):
        self._prices = price_reader or DjangoPaymentPriceReader()

    def payable(self, merchant_id: UUID, payable_type: str, payable_id: UUID, options: dict):
        if payable_type != "subscription":
            return None
        result = self.subscription_payable(
            merchant_id, options.get("plan_code", ""), options.get("period_days", 0)
        )
        if result is not None:
            result["payable_id"] = merchant_id
        return result

    def subscription_payable(self, merchant_id: UUID, plan_code: str, period_days: int):
        price = self._prices.subscription_price(merchant_id, plan_code, period_days)
        if price is None:
            return None
        return {
            "merchant_id": merchant_id,
            "country": price["country"],
            "plan_code": plan_code,
            "period_days": period_days,
            "amount_minor": price["amount_minor"],
            "currency": price["currency"],
        }

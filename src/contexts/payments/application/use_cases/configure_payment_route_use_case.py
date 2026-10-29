from shared_kernel.application_exceptions import ValidationException

from ..ports.payment_ports import IPaymentRouteAdminRepository


class ConfigurePaymentRouteUseCase:
    """Configure one country/currency/method provider route (INV-PAY-04)."""

    METHODS = {"card", "mobile_money", "bank", "manual"}

    def __init__(self, routes: IPaymentRouteAdminRepository):
        self._routes = routes

    def execute(self, country, currency, method, provider_code, priority=100,
                active=True, supports_escrow=False, config=None):
        if not isinstance(country, str) or len(country) != 2:
            raise ValidationException("Country must be an ISO alpha-2 code.")
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
            raise ValidationException("Currency must be an ISO alpha-3 code.")
        if method not in self.METHODS or not provider_code:
            raise ValidationException("Payment method or provider code is invalid.")
        if supports_escrow:
            raise ValidationException("Escrow is unavailable until a licensed provider and legal approval are configured.")
        self._routes.upsert({
            "country": country.upper(), "currency": currency.upper(),
            "method": method, "provider_code": provider_code.lower(),
            "priority": priority, "active": bool(active),
            "supports_escrow": False, "config": config or {},
        })
        return {"country": country.upper(), "currency": currency.upper(),
                "method": method, "providerCode": provider_code.lower(), "active": bool(active)}

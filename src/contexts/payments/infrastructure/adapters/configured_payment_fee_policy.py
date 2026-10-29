from django.conf import settings


class ConfiguredPaymentFeePolicy:
    """Calculate and snapshot configured platform fees at attempt creation (INV-PAY-05)."""

    def fee_minor(self, amount_minor: int, currency: str) -> int:
        basis_points = settings.PAYMENT_PLATFORM_FEE_BASIS_POINTS
        fixed_minor = settings.PAYMENT_PLATFORM_FEE_FIXED_MINOR.get(currency.upper(), 0)
        return (amount_minor * basis_points + 5000) // 10000 + fixed_minor

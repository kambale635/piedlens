from django.utils import timezone


class SystemBillingClock:
    """Provide timezone-aware UTC instants to Billing application services."""

    def now(self):
        return timezone.now()
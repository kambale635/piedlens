from datetime import timedelta

from django.conf import settings


class DjangoReminderPolicyProvider:
    """Resolve reminder delays from deployment configuration, not application logic."""

    def delay_for(self, order, reminder_type):
        """Return the configured delay for a reminder type in seconds."""
        seconds = settings.ORDER_REMINDER_DELAYS_SECONDS.get(reminder_type.value)
        return timedelta(seconds=seconds) if seconds is not None else timedelta(0)
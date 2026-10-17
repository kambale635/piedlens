from datetime import timedelta
from typing import Protocol

from ...domain.entities.order import Order
from ...domain.entities.reminder import ReminderType


class IReminderPolicyProvider(Protocol):
    """Resolve reminder timing from merchant rules or plan defaults."""

    def delay_for(self, order: Order, reminder_type: ReminderType) -> timedelta:
        """Return the configured delay without embedding a locale or plan rule."""
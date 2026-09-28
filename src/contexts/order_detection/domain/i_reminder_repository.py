from datetime import datetime
from typing import Protocol
from uuid import UUID

from .reminder import Reminder, ReminderType


class IReminderRepository(Protocol):
    """Persistence port for the Reminder aggregate."""

    def has_scheduled(self, order_id: UUID, reminder_type: ReminderType) -> bool:
        """Check the INV-OD-06 key before creating a scheduled reminder."""

    def find_by_id(self, reminder_id: UUID) -> Reminder | None:
        """Reload a claimed Reminder after acquiring its row lock."""

    def save(self, reminder: Reminder) -> None:
        """Persist a Reminder inside the active Order Detection transaction."""

    def claim_due(
        self,
        now: datetime,
        lease_until: datetime,
        limit: int,
    ) -> list[Reminder]:
        """Claim due rows and recover processing rows whose lease has expired."""
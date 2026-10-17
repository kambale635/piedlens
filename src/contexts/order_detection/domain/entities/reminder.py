from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ReminderType(StrEnum):
    """Kinds of reminders supported by the Order Detection contract."""

    PAYMENT_PENDING = "payment_pending"
    DELIVERY_PENDING = "delivery_pending"


class ReminderStatus(StrEnum):
    """Lifecycle states persisted for a reminder job."""

    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    SENT = "sent"
    PROPOSED = "proposed"
    CANCELLED = "cancelled"
    PROCESSED = "processed"


@dataclass
class Reminder:
    """Represents a scheduled reminder as its own Order Detection aggregate.

    Creating a Reminder never modifies its related Order. Its state is owned by
    this aggregate, and INV-OD-06 is additionally enforced by a conditional
    database uniqueness constraint on scheduled `(orderId, reminderType)` pairs.
    See docs/02-domain-model.md and docs/16-business-invariants-and-rules.md.
    """

    id: UUID
    order_id: UUID
    reminder_type: ReminderType
    scheduled_for: datetime
    custom_message: str | None
    _status: ReminderStatus
    attempt_count: int = 0
    lease_until: datetime | None = None
    lease_token: UUID | None = None
    next_attempt_at: datetime | None = None

    @classmethod
    def schedule(
        cls,
        order_id: UUID,
        reminder_type: ReminderType,
        scheduled_for: datetime,
        custom_message: str | None,
    ) -> "Reminder":
        """Create a scheduled reminder without changing the Order aggregate."""
        return cls(
            id=uuid4(),
            order_id=order_id,
            reminder_type=reminder_type,
            scheduled_for=scheduled_for,
            custom_message=custom_message,
            _status=ReminderStatus.SCHEDULED,
        )

    @property
    def status(self) -> ReminderStatus:
        """Return the reminder state without exposing direct mutation."""
        return self._status

    def claim(self, lease_until: datetime) -> UUID:
        """Mark the reminder as claimed until a worker completes or its lease expires."""
        self._status = ReminderStatus.PROCESSING
        self.lease_until = lease_until
        self.lease_token = uuid4()
        return self.lease_token

    def mark_sent(self) -> None:
        """Mark successful delivery as terminal so it cannot be sent again."""
        self._status = ReminderStatus.SENT
        self.lease_until = None
        self.lease_token = None
        self.next_attempt_at = None

    def mark_proposed(self) -> None:
        """Mark a Starter reminder as manually proposed, not externally sent."""
        self._status = ReminderStatus.PROPOSED
        self.lease_until = None
        self.lease_token = None

    def mark_cancelled(self) -> None:
        """Stop a reminder whose Order state no longer makes it relevant."""
        self._status = ReminderStatus.CANCELLED
        self.lease_until = None
        self.lease_token = None

    def mark_processed(self) -> None:
        """Mark an anomalous stale claim terminal after its event was already handled."""
        self._status = ReminderStatus.PROCESSED
        self.lease_until = None
        self.lease_token = None

    def schedule_retry(self, next_attempt_at: datetime) -> None:
        """Return a failed delivery to the scheduled queue with a policy timestamp."""
        self.attempt_count += 1
        self._status = ReminderStatus.SCHEDULED
        self.lease_until = None
        self.lease_token = None
        self.next_attempt_at = next_attempt_at
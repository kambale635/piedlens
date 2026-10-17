from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ...domain.entities.order import Order
from ...domain.entities.reminder import Reminder


class ReminderDeliveryMode(StrEnum):
    """Plan-configured handling mode for a due reminder."""

    MANUAL_PROPOSAL = "manual_proposal"
    AUTOMATIC_SEND = "automatic_send"


@dataclass(frozen=True)
class ReminderDeliveryResult:
    """Safe result returned by a platform-independent delivery gateway."""

    succeeded: bool
    failure_code: str | None = None


class IReminderDeliveryPolicy(Protocol):
    """Resolve manual-vs-automatic handling from merchant subscription configuration."""

    def mode_for(self, order: Order) -> ReminderDeliveryMode:
        """Return the configured plan mode without hard-coded role/plan checks."""


class IReminderMessageProvider(Protocol):
    """Resolve a localized/configured reminder message for an order."""

    def render(self, reminder: Reminder, order: Order) -> str:
        """Return configured content; no language or currency text is hard-coded here."""


class IReminderDelivery(Protocol):
    """Send through Platform Connectors without leaking connector implementations."""

    def send(
        self,
        merchant_id: UUID,
        contact_id: UUID,
        content: str,
        idempotency_key: UUID,
    ) -> ReminderDeliveryResult:
        """Attempt delivery; adapters must deduplicate repeated idempotency keys."""


class IReminderRetryPolicy(Protocol):
    """Calculate retry timing from configured operational policy."""

    def next_attempt_at(self, attempt_count: int, failed_at: datetime) -> datetime:
        """Return the next attempt time; backoff parameters belong to configuration."""
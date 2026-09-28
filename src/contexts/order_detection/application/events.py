from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


@dataclass(frozen=True)
class OrderDetected:
    """Outbox event emitted when an Order detection is accepted automatically."""

    order_id: UUID
    merchant_id: UUID
    contact_id: UUID
    source_message_id: UUID
    detected_amount: Money
    confidence_score: ConfidenceScore
    source_candidate_id: UUID | None = None


@dataclass(frozen=True)
class OrderStatusChanged:
    """Outbox event emitted after an Order aggregate accepts a valid transition."""

    order_id: UUID
    merchant_id: UUID
    contact_id: UUID
    previous_status: str
    status: str
    updated_at: datetime
    triggered_by: str
    detected_amount: Money


@dataclass(frozen=True)
class ReminderScheduled:
    """Outbox event used by the relay to enqueue a deferred reminder job."""

    reminder_id: UUID
    order_id: UUID
    reminder_type: str
    scheduled_for: datetime
    occurred_at: datetime


@dataclass(frozen=True)
class ReminderSent:
    """Confirms an idempotently delivered reminder."""

    reminder_id: UUID
    order_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ReminderProposed:
    """Signals that the merchant must send this reminder manually."""

    reminder_id: UUID
    order_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ReminderCancelled:
    """Signals that a reminder became irrelevant after its Order changed state."""

    reminder_id: UUID
    order_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ReminderDeliveryFailed:
    """Records a failed attempt and its configured retry time without message content."""

    reminder_id: UUID
    order_id: UUID
    failure_code: str | None
    next_attempt_at: datetime
    occurred_at: datetime


@dataclass(frozen=True)
class DetectionCandidateCreated:
    """Outbox event emitted when a low-confidence candidate needs review."""

    candidate_id: UUID
    merchant_id: UUID
    contact_id: UUID
    source_message_id: UUID
    detected_amount: Money
    confidence_score: ConfidenceScore


@dataclass(frozen=True)
class DetectionCandidatePromoted:
    """Carries an approved candidate to the separate Order-creation consumer."""

    candidate_id: UUID
    merchant_id: UUID
    contact_id: UUID
    source_message_id: UUID
    detected_amount: Money
    confidence_score: ConfidenceScore
    matched_rule_ids: tuple[UUID, ...]
    event_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class DetectionCandidateRejected:
    """Notifies consumers that a merchant rejected a candidate."""

    candidate_id: UUID
    merchant_id: UUID


@dataclass(frozen=True)
class DetectionCorrectedByMerchant:
    """Feeds one explicit merchant correction back to the Rules Engine."""

    merchant_id: UUID
    rule_id: UUID
    was_correct: bool
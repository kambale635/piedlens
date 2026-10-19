from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from shared_kernel.application_exceptions import OutboundQuotaExceededException
from shared_kernel.ports import IManualMessageLinkBuilder, IOutboundUsageRecorder

from ...domain.entities.order import Order
from ...domain.repositories.i_order_repository import IOrderRepository
from ...domain.value_objects.order_status import OrderStatus
from ...domain.repositories.i_reminder_repository import IReminderRepository
from ...domain.entities.reminder import Reminder, ReminderStatus, ReminderType
from ...domain.events.order_detection_events import (
    ReminderCancelled,
    ReminderDeliveryFailed,
    ReminderProposed,
    ReminderSent,
)
from ..ports.i_processed_event_repository import IProcessedEventRepository
from ..ports import IClock, IOrderDetectionOutbox, IOrderDetectionUnitOfWork
from ..dto.reminder_delivery import (
    IReminderDelivery,
    IReminderDeliveryPolicy,
    IReminderMessageProvider,
    IReminderRetryPolicy,
    ReminderDeliveryMode,
)


@dataclass(frozen=True)
class SendScheduledRemindersResult:
    """Counts of automatic sends, manual proposals, and failed attempts in one batch."""

    sent_count: int
    proposed_count: int
    failed_count: int


class SendScheduledRemindersUseCase:
    """Claim and process due reminders with retry and idempotent external delivery.

    Trigger: scheduled worker job; contract: docs/15-use-cases-catalog.md#contexte-order-detection.
    Plan policy chooses manual proposal or automatic delivery. External sends occur
    outside database transactions and use Reminder id as idempotency key; state,
    outbox and processed marker are committed together afterward (INV-TR-02/03).

    Args:
        order_repository: reads order state and merchant/contact routing identifiers.
        reminder_repository: claims due reminders and persists their independent aggregate.
        processed_events: idempotency ledger keyed by reminder id and consumer name.
        delivery_policy: resolves plan mode without a hard-coded plan comparison.
        message_provider: resolves configured/localized message content.
        delivery: platform-independent sender requiring idempotency support.
        retry_policy: calculates configured retry/backoff timing.
        unit_of_work: transaction and row-lock boundary for claim/finalization.
        outbox: stores sent/proposed/cancelled/failed events transactionally.
        clock: provides current UTC time.
        batch_limit: maximum reminders claimed in one job execution.
        lease_duration: recovery timeout for reminders claimed by a crashed worker.

    Returns:
        Counts of sent, manually proposed, and failed reminders in the batch.

    Raises:
        ValueError: if batch limit or lease duration is invalid.

    Protects INV-TR-01/02/03 and plan-based reminder limits in docs/16-business-invariants-and-rules.md.
    """

    CONSUMER_NAME = "order-detection-scheduled-reminders-consumer"

    def __init__(
        self,
        order_repository: IOrderRepository,
        reminder_repository: IReminderRepository,
        processed_events: IProcessedEventRepository,
        delivery_policy: IReminderDeliveryPolicy,
        message_provider: IReminderMessageProvider,
        delivery: IReminderDelivery,
        retry_policy: IReminderRetryPolicy,
        unit_of_work: IOrderDetectionUnitOfWork,
        outbox: IOrderDetectionOutbox,
        clock: IClock,
        batch_limit: int,
        lease_duration: timedelta,
        manual_link_builder: IManualMessageLinkBuilder,
        outbound_usage: IOutboundUsageRecorder,
    ) -> None:
        """Receive every policy, infrastructure port, and worker setting explicitly."""
        if batch_limit <= 0 or lease_duration <= timedelta(0):
            raise ValueError("batch_limit and lease_duration must be positive.")
        self._order_repository = order_repository
        self._reminder_repository = reminder_repository
        self._processed_events = processed_events
        self._delivery_policy = delivery_policy
        self._message_provider = message_provider
        self._delivery = delivery
        self._retry_policy = retry_policy
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock
        self._batch_limit = batch_limit
        self._lease_duration = lease_duration
        self._manual_link_builder = manual_link_builder
        self._outbound_usage = outbound_usage

    def execute(self) -> SendScheduledRemindersResult:
        """Claim a bounded batch and finalize each result with lease ownership checks."""
        claimed_at = self._clock.now()
        with self._unit_of_work:
            reminders = self._reminder_repository.claim_due(
                now=claimed_at,
                lease_until=claimed_at + self._lease_duration,
                limit=self._batch_limit,
            )

        sent_count = 0
        proposed_count = 0
        failed_count = 0
        for reminder in reminders:
            if self._processed_events.has_processed(reminder.id, self.CONSUMER_NAME):
                self._finalize_processed_claim(reminder)
                continue

            order = self._order_repository.find_by_id(reminder.order_id)
            if order is None or not self._is_applicable(reminder, order):
                self._finalize_cancelled(reminder)
                continue

            content = reminder.custom_message or self._message_provider.render(reminder, order)
            mode = self._delivery_policy.mode_for(order)
            if mode is ReminderDeliveryMode.MANUAL_LINK:
                manual_link = self._manual_link_builder.create_link(
                    order.merchant_id, order.contact_id, content
                )
                if self._finalize_proposed(reminder, manual_link):
                    proposed_count += 1
                continue

            try:
                self._outbound_usage.reserve(
                    order.merchant_id, "utility", f"reminder:{reminder.id}"
                )
            except OutboundQuotaExceededException:
                continue

            delivery_result = self._delivery.send(
                merchant_id=order.merchant_id,
                contact_id=order.contact_id,
                content=content,
                idempotency_key=reminder.id,
            )
            if delivery_result.succeeded:
                if self._finalize_sent(reminder):
                    sent_count += 1
            else:
                if self._finalize_failed(reminder, delivery_result.failure_code):
                    failed_count += 1

        return SendScheduledRemindersResult(
            sent_count=sent_count,
            proposed_count=proposed_count,
            failed_count=failed_count,
        )

    @staticmethod
    def _is_applicable(reminder: Reminder, order: Order) -> bool:
        required_status = {
            ReminderType.PAYMENT_PENDING: OrderStatus.PENDING_PAYMENT,
            ReminderType.DELIVERY_PENDING: OrderStatus.PAID_NOT_DELIVERED,
        }[reminder.reminder_type]
        return order.status is required_status

    def _finalize_proposed(self, claimed: Reminder, manual_link: str) -> bool:
        with self._unit_of_work:
            reminder = self._load_owned_claim(claimed)
            if reminder is None:
                return False
            reminder.mark_proposed()
            self._reminder_repository.save(reminder)
            self._outbox.add(
                ReminderProposed(
                    reminder_id=reminder.id,
                    order_id=reminder.order_id,
                    occurred_at=self._clock.now(),
                    manual_link=manual_link,
                )
            )
            self._processed_events.mark_processed(reminder.id, self.CONSUMER_NAME)
        return True

    def _finalize_sent(self, claimed: Reminder) -> bool:
        with self._unit_of_work:
            reminder = self._load_owned_claim(claimed)
            if reminder is None:
                return False
            reminder.mark_sent()
            self._reminder_repository.save(reminder)
            self._outbox.add(
                ReminderSent(reminder_id=reminder.id, order_id=reminder.order_id, occurred_at=self._clock.now())
            )
            self._processed_events.mark_processed(reminder.id, self.CONSUMER_NAME)
        return True

    def _finalize_cancelled(self, claimed: Reminder) -> None:
        with self._unit_of_work:
            reminder = self._load_owned_claim(claimed)
            if reminder is None:
                return
            reminder.mark_cancelled()
            self._reminder_repository.save(reminder)
            self._outbox.add(
                ReminderCancelled(reminder_id=reminder.id, order_id=reminder.order_id, occurred_at=self._clock.now())
            )
            self._processed_events.mark_processed(reminder.id, self.CONSUMER_NAME)

    def _finalize_failed(self, claimed: Reminder, failure_code: str | None) -> bool:
        with self._unit_of_work:
            reminder = self._load_owned_claim(claimed)
            if reminder is None:
                return False
            failed_at = self._clock.now()
            next_attempt_at = self._retry_policy.next_attempt_at(
                reminder.attempt_count + 1,
                failed_at,
            )
            reminder.schedule_retry(next_attempt_at)
            self._reminder_repository.save(reminder)
            self._outbox.add(
                ReminderDeliveryFailed(
                    reminder_id=reminder.id,
                    order_id=reminder.order_id,
                    failure_code=failure_code,
                    next_attempt_at=next_attempt_at,
                    occurred_at=failed_at,
                )
            )
        return True

    def _finalize_processed_claim(self, claimed: Reminder) -> None:
        with self._unit_of_work:
            reminder = self._load_owned_claim(claimed)
            if reminder is None:
                return
            reminder.mark_processed()
            self._reminder_repository.save(reminder)

    def _load_owned_claim(self, claimed: Reminder) -> Reminder | None:
        self._unit_of_work.lock_reminder(claimed.id)
        current = self._reminder_repository.find_by_id(claimed.id)
        if (
            current is None
            or current.status is not ReminderStatus.PROCESSING
            or current.lease_token != claimed.lease_token
            or current.lease_until is None
            or current.lease_until <= self._clock.now()
        ):
            return None
        return current
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from shared_kernel.application_exceptions import (
    PlanUpgradeRequiredException,
    ResourceNotFoundException,
    ValidationException,
)
from shared_kernel.ports import IEntitlementReader

from ...domain.repositories.i_order_repository import IOrderRepository
from ...domain.repositories.i_reminder_repository import IReminderRepository
from ...domain.value_objects.order_status import OrderStatus
from ...domain.entities.reminder import Reminder, ReminderType
from ...domain.events.order_detection_events import ReminderScheduled
from ..ports import IClock, IOrderDetectionOutbox, IOrderDetectionUnitOfWork
from ..exceptions.reminder_exceptions import ReminderAlreadyScheduledException
from ..ports.reminder_policy import IReminderPolicyProvider


@dataclass(frozen=True)
class ScheduleReminderResult:
    """Identifier and execution time of a newly scheduled reminder."""

    reminder_id: UUID
    scheduled_for: datetime


class ScheduleReminderUseCase:
    """Schedule one reminder using injected merchant/plan policy and an outbox event.

    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.
    Reminder is a separate aggregate; its creation never modifies Order (INV-TR-01).
    The reminder row and `ReminderScheduled` outbox event commit atomically (INV-TR-02).

    Args:
        order_repository: loads and locks the source Order.
        reminder_repository: persists reminders and checks scheduled duplicates.
        policy_provider: supplies merchant/plan-specific delay; no delay is hard-coded.
        unit_of_work: transaction boundary shared by reminder and outbox writes.
        outbox: stores the event for deferred scheduler delivery.
        clock: supplies the current UTC instant.

    Returns:
        Reminder id and configured execution timestamp.

    Raises:
        ValidationException: for unsupported type or non-positive configured delay.
        ResourceNotFoundException: when the Order does not exist.
        ReminderAlreadyScheduledException: when INV-OD-06 would be violated.

    Protects INV-OD-06 and INV-TR-01/02.
    """

    def __init__(
        self,
        order_repository: IOrderRepository,
        reminder_repository: IReminderRepository,
        policy_provider: IReminderPolicyProvider,
        unit_of_work: IOrderDetectionUnitOfWork,
        outbox: IOrderDetectionOutbox,
        clock: IClock,
        entitlements: IEntitlementReader,
    ) -> None:
        """Receive order, reminder, policy, transaction, outbox and clock dependencies."""
        self._order_repository = order_repository
        self._reminder_repository = reminder_repository
        self._policy_provider = policy_provider
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock
        self._entitlements = entitlements

    def execute(
        self,
        order_id: UUID,
        reminder_type: str,
        custom_message: str | None = None,
        merchant_id: UUID | None = None,
    ) -> ScheduleReminderResult:
        """Persist the reminder and scheduling event in a single database transaction."""
        try:
            normalized_type = ReminderType(reminder_type)
        except ValueError as error:
            raise ValidationException("Unsupported reminder type.") from error

        with self._unit_of_work:
            self._unit_of_work.lock_order(order_id)
            order = self._order_repository.find_by_id(order_id)
            if order is None or (merchant_id is not None and order.merchant_id != merchant_id):
                raise ResourceNotFoundException("Order was not found.")

            reminder_modes = self._entitlements.entitlements_for(
                order.merchant_id
            ).get("reminder_modes", [])
            if not isinstance(reminder_modes, list) or not reminder_modes:
                raise PlanUpgradeRequiredException("reminder_modes")

            applicable_status = {
                ReminderType.PAYMENT_PENDING: OrderStatus.PENDING_PAYMENT,
                ReminderType.DELIVERY_PENDING: OrderStatus.PAID_NOT_DELIVERED,
            }[normalized_type]
            if order.status is not applicable_status:
                raise ValidationException("Reminder type does not apply to the Order status.")

            delay = self._policy_provider.delay_for(order, normalized_type)
            if not isinstance(delay, timedelta) or delay <= timedelta(0):
                raise ValidationException("Configured reminder delay must be positive.")

            if self._reminder_repository.has_scheduled(order_id, normalized_type):
                raise ReminderAlreadyScheduledException(
                    "A reminder of this type is already scheduled for the Order."
                )

            scheduled_at = self._clock.now() + delay
            reminder = Reminder.schedule(
                order_id=order.id,
                reminder_type=normalized_type,
                scheduled_for=scheduled_at,
                custom_message=custom_message,
            )
            self._reminder_repository.save(reminder)
            self._outbox.add(
                ReminderScheduled(
                    reminder_id=reminder.id,
                    order_id=order.id,
                    reminder_type=normalized_type.value,
                    scheduled_for=scheduled_at,
                    occurred_at=self._clock.now(),
                )
            )

        return ScheduleReminderResult(
            reminder_id=reminder.id,
            scheduled_for=scheduled_at,
        )
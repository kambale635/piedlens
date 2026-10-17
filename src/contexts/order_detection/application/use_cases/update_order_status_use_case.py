from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from shared_kernel.application_exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

from ...domain.exceptions.order_detection_exceptions import InvalidOrderTransitionException
from ...domain.repositories.i_order_repository import IOrderRepository
from ...domain.value_objects.order_status import OrderStatus
from ...domain.events.order_detection_events import OrderStatusChanged
from ..ports import IClock, IOrderDetectionOutbox, IOrderDetectionUnitOfWork


class OrderStatusChangeActor(StrEnum):
    """Actors allowed by the catalogued order-status command."""

    SYSTEM = "system"
    MERCHANT = "merchant"


@dataclass(frozen=True)
class UpdateOrderStatusResult:
    """Result of a successful Order status transition."""

    order_id: UUID
    status: str
    updated_at: datetime


class UpdateOrderStatusUseCase:
    """Apply one valid Order status transition and append its event atomically.

    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.
    The aggregate owns transition validation; this application service only loads,
    delegates, persists and writes the event to the transactional outbox.

    Args:
        order_repository: Order Detection persistence port.
        unit_of_work: transaction boundary for the locked Order and outbox.
        outbox: writes `OrderStatusChanged` in the Order transaction.
        clock: provides a timezone-aware timestamp for the status transition.

    Returns:
        Order id, resulting status, and transition timestamp.

    Raises:
        ResourceNotFoundException: when the Order id does not exist.
        ValidationException: when status or actor is outside the public contract.
        InvalidOrderTransitionException: when the aggregate rejects the transition (INV-OD-01).

    Protects INV-OD-01 and INV-TR-01/02.
    """

    def __init__(
        self,
        order_repository: IOrderRepository,
        unit_of_work: IOrderDetectionUnitOfWork,
        outbox: IOrderDetectionOutbox,
        clock: IClock,
    ) -> None:
        """Receive repository, transaction, outbox and time dependencies."""
        self._order_repository = order_repository
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(
        self,
        order_id: UUID,
        new_status: str,
        triggered_by: str,
        merchant_id: UUID | None = None,
    ) -> UpdateOrderStatusResult:
        """Change and persist an Order status with a transactional domain event."""
        try:
            target_status = OrderStatus(new_status)
        except ValueError as error:
            raise ValidationException("Unsupported Order status.") from error
        try:
            actor = OrderStatusChangeActor(triggered_by)
        except ValueError as error:
            raise ValidationException("Actor must be 'system' or 'merchant'.") from error

        with self._unit_of_work:
            self._unit_of_work.lock_order(order_id)
            order = self._order_repository.find_by_id(order_id)
            if order is None or (merchant_id is not None and order.merchant_id != merchant_id):
                raise ResourceNotFoundException("Order was not found.")

            previous_status = order.status
            updated_at = self._clock.now()
            try:
                order.change_status(target_status, occurred_at=updated_at)
            except InvalidOrderTransitionException:
                raise

            self._order_repository.save(order)
            self._outbox.add(
                OrderStatusChanged(
                    order_id=order.id,
                    merchant_id=order.merchant_id,
                    contact_id=order.contact_id,
                    previous_status=previous_status.value,
                    status=order.status.value,
                    updated_at=updated_at,
                    triggered_by=actor.value,
                    detected_amount=order.detected_amount,
                )
            )

        return UpdateOrderStatusResult(
            order_id=order.id,
            status=order.status.value,
            updated_at=updated_at,
        )
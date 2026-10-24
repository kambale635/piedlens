from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.events.order_detection_events import OrderStatusChanged
from ...domain.repositories.i_order_repository import IOrderRepository
from ...domain.value_objects.order_status import OrderStatus
from ..ports import (
    IOrderDetectionOutbox,
    IOrderDetectionUnitOfWork,
    IOrderStatusIntentReader,
)
from ..ports.detection_configuration import IDetectionConfiguration
from ..ports.i_processed_event_repository import IProcessedEventRepository


@dataclass(frozen=True)
class ReconcileOrderStatusResult:
    """Outcome of applying one configured payment or delivery message."""

    outcome: str
    order_id: UUID | None = None
    status: str | None = None


class ReconcileOrderStatusFromMessageUseCase:
    """Apply configured message status signals to one existing Order.

    Trigger: `MessageEvaluated` from the Rules Engine. Intent labels and their
    target statuses come from persisted Rules Engine configuration; message
    vocabulary is not embedded in the Order domain.
    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.

    The consumer locks the Contact correlation key, locks candidate Orders,
    changes only the newest compatible Order through `Order.change_status()`,
    and commits its idempotency marker and Outbox event with that aggregate.
    It never creates an Order (INV-OD-01/02/09, INV-TR-01/02/03).
    """

    CONSUMER_NAME = "order-status-message-consumer"

    def __init__(
        self,
        order_repository: IOrderRepository,
        processed_events: IProcessedEventRepository,
        configuration: IDetectionConfiguration,
        intent_reader: IOrderStatusIntentReader,
        unit_of_work: IOrderDetectionUnitOfWork,
        outbox: IOrderDetectionOutbox,
    ) -> None:
        """Receive order, idempotency, configuration, transaction and Outbox ports."""
        self._orders = order_repository
        self._processed_events = processed_events
        self._configuration = configuration
        self._intent_reader = intent_reader
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(
        self,
        event_id: UUID,
        merchant_id: UUID,
        contact_id: UUID,
        intent: str | None,
        source_message_id: UUID,
        source_message_timestamp: datetime,
    ) -> ReconcileOrderStatusResult:
        """Reconcile a configured status signal idempotently within its source-time window."""
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return ReconcileOrderStatusResult("already_processed")

            self._unit_of_work.lock_detection_contact(contact_id)
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return ReconcileOrderStatusResult("already_processed")

            configured_intents = self._intent_reader.configured_intents(merchant_id)
            target_status = self._target_status(intent) if intent in configured_intents else None
            if target_status is None:
                self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
                return ReconcileOrderStatusResult("ignored")

            configuration = self._configuration.for_merchant(merchant_id)
            expected_status = {
                OrderStatus.PAID_NOT_DELIVERED: OrderStatus.PENDING_PAYMENT,
                OrderStatus.PAID_AND_DELIVERED: OrderStatus.PAID_NOT_DELIVERED,
            }[target_status]
            candidates = self._orders.find_orders_for_status_reconciliation(
                merchant_id=merchant_id,
                contact_id=contact_id,
                expected_status=expected_status.value,
                source_timestamp=source_message_timestamp,
                within_days=configuration.correlation_window_days,
            )
            if not candidates:
                self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
                return ReconcileOrderStatusResult("ignored")

            order = max(candidates, key=lambda item: (item.created_at, str(item.id)))
            previous_status = order.status.value
            order.change_status(target_status, occurred_at=source_message_timestamp)
            self._orders.save(order)
            self._outbox.add(
                OrderStatusChanged(
                    order_id=order.id,
                    merchant_id=order.merchant_id,
                    contact_id=order.contact_id,
                    previous_status=previous_status,
                    status=order.status.value,
                    updated_at=source_message_timestamp,
                    triggered_by="system",
                    detected_amount=order.detected_amount,
                )
            )
            self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)

        return ReconcileOrderStatusResult("updated", order.id, order.status.value)

    @staticmethod
    def _target_status(intent: str | None) -> OrderStatus | None:
        """Map the configured status-intent contract to its permitted Order state."""
        return {
            "payment_received": OrderStatus.PAID_NOT_DELIVERED,
            "delivery_confirmed": OrderStatus.PAID_AND_DELIVERED,
        }.get(intent)
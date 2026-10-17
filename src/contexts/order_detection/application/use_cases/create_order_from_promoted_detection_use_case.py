from dataclasses import dataclass
from uuid import UUID

from ...domain.repositories.i_order_repository import IOrderRepository
from ...domain.entities.order import Order
from ...domain.events.order_detection_events import DetectionCandidatePromoted, OrderDetected
from ..ports.i_contact_reference_redirect_repository import IContactReferenceRedirectRepository
from ..ports.i_processed_event_repository import IProcessedEventRepository
from ..ports import IOrderDetectionOutbox, IPromotedCandidateOrderUnitOfWork


@dataclass(frozen=True)
class CreateOrderFromPromotedDetectionResult:
    """Result of consuming one candidate-promotion event."""

    order_id: UUID | None
    created: bool


class CreateOrderFromPromotedDetectionUseCase:
    """Create one Order from an approved candidate in an idempotent transaction.

    Trigger: `DetectionCandidatePromoted` from consumer group
    `order-detection-promotion-consumer`.
    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.

    Args:
        order_repository: Order persistence port with a unique candidate lookup.
        processed_events: idempotency port sharing the transaction with Order and outbox.
        contact_redirects: Order Detection-owned view of CRM Contact redirects.
        unit_of_work: transaction and per-candidate serialization boundary.
        outbox: transactional producer outbox for the resulting `OrderDetected`.

    Returns:
        The created or already-created Order id; `created` is false on redelivery.

    Raises:
        Infrastructure failures propagate so the stream worker can retry or dead-letter.

    Protects INV-OD-04, INV-OD-07, INV-TR-01, INV-TR-02, and INV-TR-03.
    """

    CONSUMER_NAME = "order-detection-promotion-consumer"

    def __init__(
        self,
        order_repository: IOrderRepository,
        processed_events: IProcessedEventRepository,
        contact_redirects: IContactReferenceRedirectRepository,
        unit_of_work: IPromotedCandidateOrderUnitOfWork,
        outbox: IOrderDetectionOutbox,
    ) -> None:
        """Receive all persistence and transaction dependencies through ports."""
        self._order_repository = order_repository
        self._processed_events = processed_events
        self._contact_redirects = contact_redirects
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(
        self, event: DetectionCandidatePromoted
    ) -> CreateOrderFromPromotedDetectionResult:
        """Consume one event; atomically save Order, outbox event, and processed marker."""
        with self._unit_of_work:
            self._unit_of_work.lock_candidate_creation(event.candidate_id)
            self._unit_of_work.lock_detection_contact(event.contact_id)
            contact_id = self._resolve_and_lock_contact(event.merchant_id, event.contact_id)

            existing_order = self._order_repository.find_by_source_candidate_id(
                event.candidate_id
            )
            if self._processed_events.has_processed(event.event_id, self.CONSUMER_NAME):
                return CreateOrderFromPromotedDetectionResult(
                    order_id=existing_order.id if existing_order else None,
                    created=False,
                )

            if existing_order is not None:
                self._processed_events.mark_processed(event.event_id, self.CONSUMER_NAME)
                return CreateOrderFromPromotedDetectionResult(
                    order_id=existing_order.id,
                    created=False,
                )

            order = Order.detect(
                merchant_id=event.merchant_id,
                contact_id=contact_id,
                detected_amount=event.detected_amount,
                confidence_score=event.confidence_score,
                source_message_id=event.source_message_id,
                occurred_at=event.occurred_at,
                source_candidate_id=event.candidate_id,
            )
            self._order_repository.save(order)
            self._outbox.add(
                OrderDetected(
                    order_id=order.id,
                    merchant_id=order.merchant_id,
                    contact_id=order.contact_id,
                    source_message_id=event.source_message_id,
                    detected_amount=order.detected_amount,
                    confidence_score=order.confidence_score,
                    source_candidate_id=event.candidate_id,
                )
            )
            self._processed_events.mark_processed(event.event_id, self.CONSUMER_NAME)

        return CreateOrderFromPromotedDetectionResult(order_id=order.id, created=True)

    def _resolve_and_lock_contact(self, merchant_id: UUID, contact_id: UUID) -> UUID:
        """Lock and re-resolve the canonical Contact before creating the new Order."""
        resolved_contact_id = self._contact_redirects.resolve(merchant_id, contact_id)
        while resolved_contact_id != contact_id:
            self._unit_of_work.lock_detection_contact(resolved_contact_id)
            latest_contact_id = self._contact_redirects.resolve(merchant_id, contact_id)
            if latest_contact_id == resolved_contact_id:
                return resolved_contact_id
            resolved_contact_id = latest_contact_id
        return contact_id
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.value_objects.confidence_score import ConfidenceScore

from ...domain.entities.detection_candidate import DetectionCandidate
from ...domain.repositories.i_detection_candidate_repository import IDetectionCandidateRepository
from ...domain.repositories.i_order_repository import IOrderRepository
from ...domain.entities.order import Order
from ..ports.detection_configuration import IDetectionConfiguration
from ...domain.events.order_detection_events import DetectionCandidateCreated, OrderDetected
from ..dto.evaluation_result import EvaluationResult
from ..ports.i_contact_reference_redirect_repository import IContactReferenceRedirectRepository
from ..ports.i_processed_event_repository import IProcessedEventRepository
from ..ports import IOrderDetectionOutbox, IOrderDetectionUnitOfWork


@dataclass(frozen=True)
class DetectOrderResult:
    """Typed result for automatic, manual-review, or ignored detections."""

    outcome: str
    order_id: UUID | None = None
    candidate_id: UUID | None = None
    status: str | None = None


class DetectOrderUseCase:
    """Detect an Order or manual-review candidate from a Rules Engine evaluation.

    Trigger: `MessageEvaluated` (consumer group `order-detection-consumer`).
    Contract: docs/15-use-cases-catalog.md#contexte-order-detection.

    Args:
        processed_events: idempotency ledger sharing the aggregate transaction.
        order_repository: Order Detection-owned persistence port.
        candidate_repository: separate persistence port for low-confidence candidates.
        configuration: resolves the merchant's score threshold and correlation window.
            unit_of_work: transaction boundary shared by aggregate, outbox, and processed marker.
        outbox: appends producer events to `outbox_events` in that same transaction.

    Returns:
        `order_created` at or above the configured threshold, `candidate_created`
        below it, or `ignored` when intent/amount is not actionable.

    Raises:
        Domain value-object exceptions if a configured score is outside [0, 100].

    Protects INV-OD-02, INV-OD-03, INV-OD-04, INV-OD-07, and INV-TR-01/02/03.
    """

    CONSUMER_NAME = "order-detection-consumer"

    def __init__(
        self,
        processed_events: IProcessedEventRepository,
        contact_redirects: IContactReferenceRedirectRepository,
        order_repository: IOrderRepository,
        candidate_repository: IDetectionCandidateRepository,
        configuration: IDetectionConfiguration,
        unit_of_work: IOrderDetectionUnitOfWork,
        outbox: IOrderDetectionOutbox,
    ) -> None:
        """Receive all persistence, configuration, and transaction dependencies."""
        self._processed_events = processed_events
        self._contact_redirects = contact_redirects
        self._order_repository = order_repository
        self._candidate_repository = candidate_repository
        self._configuration = configuration
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(
        self,
        merchant_id: UUID,
        event_id: UUID,
        contact_id: UUID,
        evaluation_result: EvaluationResult,
        source_message_id: UUID,
        source_message_timestamp: datetime,
    ) -> DetectOrderResult:
        """Handle one evaluated message idempotently and serialize contact correlation."""
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return DetectOrderResult(outcome="already_processed")

            self._unit_of_work.lock_detection_contact(contact_id)
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return DetectOrderResult(outcome="already_processed")

            if evaluation_result.intent != "purchase" or evaluation_result.amount is None:
                self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
                return DetectOrderResult(outcome="ignored")

            resolved_contact_id = self._resolve_and_lock_contact(merchant_id, contact_id)
            configuration = self._configuration.for_merchant(merchant_id)
            threshold = ConfidenceScore(configuration.confidence_threshold)

            if evaluation_result.confidence_score.value < threshold.value:
                candidate = DetectionCandidate.create(
                    merchant_id=merchant_id,
                    contact_id=resolved_contact_id,
                    detected_amount=evaluation_result.amount,
                    confidence_score=evaluation_result.confidence_score,
                    source_message_id=source_message_id,
                    matched_rule_ids=evaluation_result.matched_rule_ids,
                    occurred_at=source_message_timestamp,
                )
                self._candidate_repository.save(candidate)
                self._outbox.add(
                    DetectionCandidateCreated(
                        candidate_id=candidate.id,
                        merchant_id=merchant_id,
                        contact_id=contact_id,
                        source_message_id=source_message_id,
                        detected_amount=candidate.detected_amount,
                        confidence_score=candidate.confidence_score,
                    )
                )
                self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
                return DetectOrderResult(
                    outcome="candidate_created",
                    candidate_id=candidate.id,
                    status="pending_review",
                )

            open_orders = self._order_repository.find_pending_by_contact(
                resolved_contact_id, configuration.correlation_window_days
            )
            if open_orders:
                order = max(open_orders, key=lambda item: item.created_at)
                order.record_amount_signal(
                    evaluation_result.amount,
                    source_message_id,
                    source_message_timestamp,
                )
            else:
                order = Order.detect(
                    merchant_id=merchant_id,
                    contact_id=resolved_contact_id,
                    detected_amount=evaluation_result.amount,
                    confidence_score=evaluation_result.confidence_score,
                    source_message_id=source_message_id,
                    occurred_at=source_message_timestamp,
                )

            self._order_repository.save(order)
            self._outbox.add(
                OrderDetected(
                    order_id=order.id,
                    merchant_id=merchant_id,
                    contact_id=resolved_contact_id,
                    source_message_id=source_message_id,
                    detected_amount=order.detected_amount,
                    confidence_score=evaluation_result.confidence_score,
                )
            )
            self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)

        return DetectOrderResult(
            outcome="order_created",
            order_id=order.id,
            status=order.status.value,
        )

    def _resolve_and_lock_contact(self, merchant_id: UUID, contact_id: UUID) -> UUID:
        """Lock and re-resolve the canonical Contact to serialize late merge events."""
        resolved_contact_id = self._contact_redirects.resolve(merchant_id, contact_id)
        while resolved_contact_id != contact_id:
            self._unit_of_work.lock_detection_contact(resolved_contact_id)
            latest_contact_id = self._contact_redirects.resolve(merchant_id, contact_id)
            if latest_contact_id == resolved_contact_id:
                return resolved_contact_id
            resolved_contact_id = latest_contact_id
        return contact_id
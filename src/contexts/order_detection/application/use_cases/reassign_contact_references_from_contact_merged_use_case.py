from dataclasses import dataclass
from uuid import UUID

from ...domain.repositories.i_detection_candidate_repository import IDetectionCandidateRepository
from ...domain.repositories.i_order_repository import IOrderRepository
from ...domain.events.order_detection_events import ContactMerged
from ..ports.i_contact_reference_redirect_repository import IContactReferenceRedirectRepository
from ..ports.i_processed_event_repository import IProcessedEventRepository
from ..ports import IOrderDetectionUnitOfWork


@dataclass(frozen=True)
class ReassignContactReferencesResult:
    """Counts references reassigned while completing one ContactMerged event."""

    reassigned_order_count: int
    reassigned_candidate_count: int


class ReassignContactReferencesFromContactMergedUseCase:
    """Reassign Order Detection references without crossing aggregate transactions.

    Trigger: CRM `ContactMerged`; contract:
    docs/15-use-cases-catalog.md#contexte-order-detection.
    Each Order and DetectionCandidate is locked, rechecked, and saved in its own
    transaction. The completion marker is written only after both scans finish;
    unfinished work can therefore be replayed safely (INV-CRM-03, INV-TR-01/03).
    The CRM snapshot is deliberately not consumed (INV-TR-04).

    Args:
        order_repository: Order Detection-owned Order query and persistence port.
        candidate_repository: Order Detection-owned candidate query and persistence port.
        processed_events: idempotency ledger for the consumer group.
        redirects: Order Detection-owned projection of CRM Contact redirects.
        unit_of_work: Order Detection transaction boundary, opened per aggregate.

    Returns:
        Counts of Orders and candidates reassigned during this invocation; a
        completed redelivery returns zero counts.

    Raises:
        Infrastructure exceptions propagate so the stream worker can retry the event.

    Protects INV-CRM-03, INV-TR-01, INV-TR-03, and INV-TR-04.
    """

    CONSUMER_NAME = "order-detection-contact-merge-consumer"

    def __init__(
        self,
        order_repository: IOrderRepository,
        candidate_repository: IDetectionCandidateRepository,
        processed_events: IProcessedEventRepository,
        redirects: IContactReferenceRedirectRepository,
        unit_of_work: IOrderDetectionUnitOfWork,
    ) -> None:
        """Receive context-owned repositories, processed-event ledger, and UoW."""
        self._order_repository = order_repository
        self._candidate_repository = candidate_repository
        self._processed_events = processed_events
        self._redirects = redirects
        self._unit_of_work = unit_of_work

    def execute(self, event: ContactMerged) -> ReassignContactReferencesResult:
        """Reassign each still-matching aggregate, then commit the completion marker."""
        with self._unit_of_work:
            if self._processed_events.has_processed(event.event_id, self.CONSUMER_NAME):
                return ReassignContactReferencesResult(0, 0)
            self._unit_of_work.lock_detection_contact(event.merged_contact_id)
            self._redirects.register(
                merchant_id=event.merchant_id,
                merged_contact_id=event.merged_contact_id,
                primary_contact_id=event.primary_contact_id,
            )

        reassigned_orders = self._reassign_orders(
            event.merged_contact_id,
            event.primary_contact_id,
        )
        reassigned_candidates = self._reassign_candidates(
            event.merged_contact_id,
            event.primary_contact_id,
        )

        with self._unit_of_work:
            if not self._processed_events.has_processed(
                event.event_id,
                self.CONSUMER_NAME,
            ):
                self._processed_events.mark_processed(
                    event.event_id,
                    self.CONSUMER_NAME,
                )

        return ReassignContactReferencesResult(
            reassigned_order_count=reassigned_orders,
            reassigned_candidate_count=reassigned_candidates,
        )

    def _reassign_orders(self, merged_contact_id: UUID, primary_contact_id: UUID) -> int:
        """Reassign Orders one aggregate transaction at a time."""
        reassigned_count = 0
        for order_id in self._order_repository.find_ids_by_contact(merged_contact_id):
            with self._unit_of_work:
                order = self._order_repository.find_for_update_by_id(order_id)
                if order is None or order.contact_id != merged_contact_id:
                    continue
                order.reassign_contact(primary_contact_id)
                self._order_repository.save(order)
                reassigned_count += 1
        return reassigned_count

    def _reassign_candidates(
        self,
        merged_contact_id: UUID,
        primary_contact_id: UUID,
    ) -> int:
        """Reassign candidates one aggregate transaction at a time."""
        reassigned_count = 0
        for candidate_id in self._candidate_repository.find_ids_by_contact(
            merged_contact_id
        ):
            with self._unit_of_work:
                candidate = self._candidate_repository.find_for_update_by_id(
                    candidate_id
                )
                if candidate is None or candidate.contact_id != merged_contact_id:
                    continue
                candidate.reassign_contact(primary_contact_id)
                self._candidate_repository.save(candidate)
                reassigned_count += 1
        return reassigned_count
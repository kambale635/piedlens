from uuid import UUID

from ...domain.events.merchant_data_purged import MerchantDataPurged
from ..ports import IOrderDetectionMerchantPurger, IOrderDetectionOutbox, IOrderDetectionUnitOfWork
from ..ports.i_processed_event_repository import IProcessedEventRepository


class PurgeMerchantDataUseCase:
    """Consume MerchantDataDeleted and purge Order Detection-owned merchant data.

    Trigger: backup.events / MerchantDataDeleted consumer group.
    Contract: docs/14-event-driven-architecture.md, docs/15-use-cases-catalog.md.
    Orders, candidates and reminders are removed as separate aggregate writes;
    progress markers make each scan resumable, and the final marker and Outbox
    confirmation are atomic (INV-OD-08, INV-BK-06, INV-TR-01/03).
    """

    CONSUMER_NAME = "order-detection.merchant-data-deleted"

    def __init__(
        self,
        purger: IOrderDetectionMerchantPurger,
        processed_events: IProcessedEventRepository,
        unit_of_work: IOrderDetectionUnitOfWork,
        outbox: IOrderDetectionOutbox,
    ) -> None:
        self._purger = purger
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(self, event_id: UUID, merchant_id: UUID) -> bool:
        """Resume local aggregate deletion and publish one completion (INV-OD-08, INV-TR-03)."""
        if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
            return False
        self._purger.purge_merchant_data(event_id, merchant_id)
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return False
            self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
            self._outbox.add(MerchantDataPurged("order-detection", merchant_id))
        return True
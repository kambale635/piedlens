from uuid import UUID

from ...domain.events.merchant_data_purged import MerchantDataPurged
from ..ports import ICRMOutbox, ICRMMerchantPurger, ICRMUnitOfWork, IProcessedMessageRepository


class PurgeMerchantDataUseCase:
    """Consume MerchantDataDeleted and purge all CRM-owned merchant data.

    Trigger: backup.events / MerchantDataDeleted consumer group.
    Contract: docs/14-event-driven-architecture.md, docs/15-use-cases-catalog.md.
    Each Contact, Segment, notification, recipient journal, and campaign is
    deleted in its own transaction with resumable progress before the final
    processed marker and Outbox event (INV-CRM-09, INV-BK-06, INV-TR-01/03).
    """

    CONSUMER_NAME = "crm.merchant-data-deleted"

    def __init__(
        self,
        purger: ICRMMerchantPurger,
        processed_events: IProcessedMessageRepository,
        unit_of_work: ICRMUnitOfWork,
        outbox: ICRMOutbox,
    ) -> None:
        self._purger = purger
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(self, event_id: UUID, merchant_id: UUID) -> bool:
        """Resume local CRM cleanup and emit one transactional completion event (INV-CRM-09, INV-TR-03)."""
        if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
            return False
        self._purger.purge_merchant_data(event_id, merchant_id)
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return False
            if not self._processed_events.mark_processed(event_id, self.CONSUMER_NAME):
                return False
            self._outbox.add(MerchantDataPurged("crm", merchant_id))
        return True
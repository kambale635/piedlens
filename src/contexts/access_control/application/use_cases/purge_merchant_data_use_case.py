from uuid import UUID

from ...domain.events.access_control_events import MerchantDataPurged
from ..ports.access_control_ports import (
    IAccessControlMerchantPurger,
    IAccessControlOutbox,
    IAccessControlUnitOfWork,
    IProcessedEventRepository,
)


class PurgeMerchantDataUseCase:
    """Consume MerchantDataDeleted and remove only merchant-scoped assignments.

    Trigger: backup.events / MerchantDataDeleted consumer group.
    Contract: docs/14-event-driven-architecture.md, docs/15-use-cases-catalog.md.
    Assignment audit identifiers are retained separately; each assignment is
    purged in a resumable transaction before the completion marker and Outbox
    event are committed (INV-AC-06, INV-BK-06, INV-TR-01, INV-TR-03).
    """

    CONSUMER_NAME = "access-control.merchant-data-deleted"

    def __init__(
        self,
        purger: IAccessControlMerchantPurger,
        processed_events: IProcessedEventRepository,
        unit_of_work: IAccessControlUnitOfWork,
        outbox: IAccessControlOutbox,
    ) -> None:
        self._purger = purger
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(self, event_id: UUID, merchant_id: UUID) -> bool:
        """Resume local assignment cleanup and publish its result once (INV-BK-06, INV-TR-03)."""
        if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
            return False
        self._purger.purge_merchant_assignments(event_id, merchant_id)
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return False
            if not self._processed_events.mark_processed(event_id, self.CONSUMER_NAME):
                return False
            self._outbox.add(MerchantDataPurged("access-control", merchant_id))
        return True
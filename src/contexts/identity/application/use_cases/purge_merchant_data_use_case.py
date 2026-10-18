from uuid import UUID

from ...domain.events.identity_events import MerchantDataPurged
from ..ports.identity_ports import (
    IIdentityOutbox,
    IIdentityProcessedEventRepository,
    IIdentityUnitOfWork,
    IMerchantRepository,
)


class PurgeMerchantDataUseCase:
    """Consume MerchantDataDeleted and purge only Identity's Merchant aggregate.

    Trigger: backup.events / MerchantDataDeleted consumer group.
    Contract: docs/14-event-driven-architecture.md, docs/15-use-cases-catalog.md.
    The Merchant deletion, idempotency marker, and MerchantDataPurged Outbox
    event share one transaction (INV-ID-07, INV-BK-06, INV-TR-01, INV-TR-03).
    User records are retained because a user may belong to other merchants.
    """

    CONSUMER_NAME = "identity.merchant-data-deleted"

    def __init__(
        self,
        merchants: IMerchantRepository,
        processed_events: IIdentityProcessedEventRepository,
        unit_of_work: IIdentityUnitOfWork,
        outbox: IIdentityOutbox,
    ) -> None:
        self._merchants = merchants
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(self, event_id: UUID, merchant_id: UUID) -> bool:
        """Apply the local purge once and atomically publish its completion (INV-BK-06, INV-TR-03)."""
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return False
            self._merchants.delete_by_id(merchant_id)
            if not self._processed_events.mark_processed(event_id, self.CONSUMER_NAME):
                return False
            self._outbox.add(MerchantDataPurged("identity", merchant_id))
        return True
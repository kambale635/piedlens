from uuid import UUID

from ...domain.events.platform_events import MerchantDataPurged
from ..ports.platform_ports import (
    IPlatformConnectorsMerchantPurger,
    IPlatformConnectorsOutbox,
    IPlatformConnectorsProcessedEventRepository,
    IPlatformConnectorsUnitOfWork,
    IPlatformClock,
)


class PurgeMerchantDataUseCase:
    """Consume MerchantDataDeleted and destroy local credentials and message data.

    Trigger: backup.events / MerchantDataDeleted consumer group.
    Contract: docs/14-event-driven-architecture.md, docs/15-use-cases-catalog.md.
    Connections are removed before messages so new writes cannot be accepted;
    each record is deleted with a durable progress marker, then completion is
    written to the local Outbox (INV-PC-05, INV-BK-06, INV-TR-01, INV-TR-03).
    """

    CONSUMER_NAME = "platform-connectors.merchant-data-deleted"

    def __init__(
        self,
        purger: IPlatformConnectorsMerchantPurger,
        processed_events: IPlatformConnectorsProcessedEventRepository,
        unit_of_work: IPlatformConnectorsUnitOfWork,
        outbox: IPlatformConnectorsOutbox,
        clock: IPlatformClock,
    ) -> None:
        self._purger = purger
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(self, event_id: UUID, merchant_id: UUID) -> bool:
        """Resume local record deletion and publish completion once (INV-PC-05, INV-TR-03)."""
        if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
            return False
        self._purger.purge_merchant_data(event_id, merchant_id)
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return False
            self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
            self._outbox.add(
                MerchantDataPurged("platform-connectors", merchant_id, self._clock.now_utc())
            )
        return True
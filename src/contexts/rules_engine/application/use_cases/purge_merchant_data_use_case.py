from uuid import UUID

from ...domain.events.merchant_data_purged import MerchantDataPurged
from ..ports.rules_engine_ports import (
    IProcessedEventRepository,
    IRulesEngineMerchantPurger,
    IRulesEngineOutbox,
    IRulesEngineUnitOfWork,
)


class PurgeMerchantDataUseCase:
    """Consume MerchantDataDeleted and remove only merchant-scoped RuleSets.

    Trigger: backup.events / MerchantDataDeleted consumer group.
    Contract: docs/14-event-driven-architecture.md, docs/15-use-cases-catalog.md.
    Country and global RuleSets remain untouched; progress, processed-event
    marker and completion Outbox follow INV-RE-05, INV-BK-06, INV-TR-01/03.
    """

    CONSUMER_NAME = "rules-engine.merchant-data-deleted"

    def __init__(
        self,
        purger: IRulesEngineMerchantPurger,
        processed_events: IProcessedEventRepository,
        unit_of_work: IRulesEngineUnitOfWork,
        outbox: IRulesEngineOutbox,
    ) -> None:
        self._purger = purger
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(self, event_id: UUID, merchant_id: UUID) -> bool:
        """Resume merchant RuleSet deletion and publish one local completion (INV-RE-05, INV-TR-03)."""
        if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
            return False
        self._purger.purge_merchant_rule_sets(event_id, merchant_id)
        with self._unit_of_work:
            if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
                return False
            if not self._processed_events.mark_processed(event_id, self.CONSUMER_NAME):
                return False
            self._outbox.add(MerchantDataPurged("rules-engine", merchant_id))
        return True
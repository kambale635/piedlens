from dataclasses import dataclass
from uuid import UUID

from shared_kernel.application_exceptions import ResourceNotFoundException

from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.events.crm_events import ContactMerged
from ..ports import ICRMUnitOfWork, IProcessedMessageRepository


@dataclass(frozen=True)
class ConsumeContactMergedResult:
    """Report whether a ContactMerged snapshot was absorbed by its primary Contact."""

    primary_contact_id: UUID
    applied: bool


class ConsumeContactMergedUseCase:
    """Absorb one immutable duplicate snapshot into the CRM primary Contact.

    Trigger: CRM `ContactMerged` event; contract:
    docs/15-use-cases-catalog.md#contexte-crm.
    Only the primary Contact is modified, and its snapshot totals are applied in
    the same transaction as the processed-event marker (INV-CRM-04, INV-TR-01/03).

    Args:
        contact_repository: CRM-owned Contact lock/read/write port.
        processed_events: CRM idempotency ledger for ContactMerged.
        unit_of_work: transaction boundary for the Contact and processed marker.

    Returns:
        The primary Contact ID and whether this event was newly applied.

    Raises:
        ResourceNotFoundException: if the primary Contact is absent or belongs to
            a different merchant than the event.

    Protects INV-CRM-04, INV-TR-01, and INV-TR-03.
    """

    CONSUMER_NAME = "crm-contact-merge-consumer"

    def __init__(
        self,
        contact_repository: IContactRepository,
        processed_events: IProcessedMessageRepository,
        unit_of_work: ICRMUnitOfWork,
    ) -> None:
        """Receive CRM persistence, idempotency, and transaction ports."""
        self._contact_repository = contact_repository
        self._processed_events = processed_events
        self._unit_of_work = unit_of_work

    def execute(self, event: ContactMerged) -> ConsumeContactMergedResult:
        """Apply the snapshot once, changing only the primary Contact aggregate."""
        with self._unit_of_work:
            if self._processed_events.has_processed(event.event_id, self.CONSUMER_NAME):
                return ConsumeContactMergedResult(
                    primary_contact_id=event.primary_contact_id,
                    applied=False,
                )

            primary = self._contact_repository.find_for_update_by_id(
                event.primary_contact_id
            )
            if primary is None or primary.merchant_id != event.merchant_id:
                raise ResourceNotFoundException("Contact was not found.")

            primary.absorb_merged_contact(
                total_spent_by_currency=event.snapshot.total_spent_by_currency,
                order_count=event.snapshot.order_count,
                purchase_history=event.snapshot.purchase_history,
                tags=event.snapshot.tags,
            )
            self._contact_repository.save(primary)
            self._processed_events.mark_processed(event.event_id, self.CONSUMER_NAME)

        return ConsumeContactMergedResult(
            primary_contact_id=primary.id,
            applied=True,
        )
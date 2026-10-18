from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_kernel.application_exceptions import ResourceNotFoundException
from shared_kernel.value_objects.money import Money

from ..ports.contact_defaults import IContactDefaultsProvider
from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.services.loyalty_score_calculator import ILoyaltyScoreCalculator
from ..ports import ICRMUnitOfWork, IProcessedMessageRepository


@dataclass(frozen=True)
class UpdateContactFromOrderResult:
    """Contact purchase totals after a delivered-order event, or an ignored-event result."""

    contact_id: UUID
    applied: bool
    total_spent_by_currency: tuple[Money, ...] = ()
    order_count: int | None = None
    loyalty_score: int | None = None


class UpdateContactFromOrderUseCase:
    """Apply delivered-order events to CRM totals exactly once per event.

    Trigger: `OrderStatusChanged`; contract: docs/15-use-cases-catalog.md#contexte-crm.
    Only `paid_and_delivered` changes Contact purchase aggregates and history (INV-CRM-04).
    Money is accumulated per currency with no implicit conversion (INV-OD-05/INV-TR-05).
    Contact and processed-event marker commit in the same CRM transaction (INV-TR-03).

    Args:
        contact_repository: CRM-owned Contact read/write port.
        loyalty_score_calculator: dedicated CRM domain service; formula is supplied by policy.
        processed_messages: idempotency ledger for the CRM Order consumer.
        unit_of_work: transaction boundary for Contact and processed marker.

    Returns:
        Updated totals and loyalty score for delivered orders; non-delivery events are
        marked processed and return `applied=False` without mutating Contact.

    Raises:
        ResourceNotFoundException: if a delivered-order event references no CRM Contact.

    Protects INV-CRM-04, INV-OD-05, INV-TR-03, and INV-TR-05.
    """

    CONSUMER_NAME = "crm-order-consumer"

    def __init__(
        self,
        contact_repository: IContactRepository,
        loyalty_score_calculator: ILoyaltyScoreCalculator | None,
        defaults_provider: IContactDefaultsProvider | None,
        processed_messages: IProcessedMessageRepository,
        unit_of_work: ICRMUnitOfWork,
    ) -> None:
        """Receive CRM persistence, scoring, idempotency and transaction ports."""
        self._contact_repository = contact_repository
        self._loyalty_score_calculator = loyalty_score_calculator
        self._defaults_provider = defaults_provider
        self._processed_messages = processed_messages
        self._unit_of_work = unit_of_work

    def execute(
        self,
        event_id: UUID,
        contact_id: UUID,
        order_id: UUID,
        status: str,
        order_amount: Money,
        updated_at: datetime,
    ) -> UpdateContactFromOrderResult:
        """Consume one status event and update only delivered-order CRM aggregates."""
        with self._unit_of_work:
            if self._processed_messages.has_processed(event_id, self.CONSUMER_NAME):
                return UpdateContactFromOrderResult(contact_id=contact_id, applied=False)

            if status != "paid_and_delivered":
                self._processed_messages.mark_processed(event_id, self.CONSUMER_NAME)
                return UpdateContactFromOrderResult(contact_id=contact_id, applied=False)

            contact = self._contact_repository.find_for_update_by_id(contact_id)
            if contact is None:
                raise ResourceNotFoundException("Contact was not found.")

            applied = contact.record_paid_order(order_id, order_amount, updated_at)
            if applied:
                if self._loyalty_score_calculator is not None:
                    primary_currency = self._defaults_provider.primary_currency(contact.merchant_id)
                    contact.update_loyalty_score(
                        self._loyalty_score_calculator.calculate(contact, primary_currency)
                    )
                self._contact_repository.save(contact)
            self._processed_messages.mark_processed(event_id, self.CONSUMER_NAME)

        return self._result(contact, applied=applied)

    @staticmethod
    def _result(contact, applied: bool) -> UpdateContactFromOrderResult:
        return UpdateContactFromOrderResult(
            contact_id=contact.id,
            applied=applied,
            total_spent_by_currency=contact.total_spent_by_currency,
            order_count=contact.order_count,
            loyalty_score=contact.loyalty_score.value,
        )
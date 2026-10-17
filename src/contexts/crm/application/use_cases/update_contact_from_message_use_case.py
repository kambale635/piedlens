from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.entities.contact import Contact
from ...domain.value_objects.contact_status import ContactStatus
from ...domain.repositories.i_contact_repository import IContactRepository
from ..ports.contact_defaults import IContactDefaultsProvider
from ..exceptions import InvalidContactIdentityException
from ..ports import ICRMUnitOfWork, IProcessedMessageRepository


@dataclass(frozen=True)
class UpdateContactFromMessageResult:
    """Contact identity and creation flag returned to the message consumer."""

    contact_id: UUID
    is_new_contact: bool


class UpdateContactFromMessageUseCase:
    """Upsert one CRM contact from MessageReceived without using display name as identity.

    Trigger: `MessageReceived`; contract: docs/15-use-cases-catalog.md#contexte-crm.
    The transaction atomically updates/creates Contact and records the event idempotency
    marker (INV-TR-03). Message timestamps older than the stored interaction do not
    overwrite newer profile state (INV-CRM-01); order totals are untouched (INV-CRM-04).

    Args:
        contact_repository: CRM persistence port keyed by merchant, connection and external id.
        defaults_provider: resolves the initial zero Money in merchant currency.
        processed_messages: eventId/consumer idempotency ledger.
        unit_of_work: atomic CRM transaction boundary.

    Returns:
        Contact id and whether this event created the contact.

    Raises:
        InvalidContactIdentityException: when the external platform identifier is empty.

    Protects INV-CRM-01, INV-CRM-04, and INV-TR-03.
    """

    CONSUMER_NAME = "crm-message-consumer"

    def __init__(
        self,
        contact_repository: IContactRepository,
        defaults_provider: IContactDefaultsProvider,
        processed_messages: IProcessedMessageRepository,
        unit_of_work: ICRMUnitOfWork,
    ) -> None:
        """Receive CRM and infrastructure ports through constructor injection."""
        self._contact_repository = contact_repository
        self._defaults_provider = defaults_provider
        self._processed_messages = processed_messages
        self._unit_of_work = unit_of_work

    def execute(
        self,
        event_id: UUID,
        merchant_id: UUID,
        platform_connection_id: UUID,
        external_identifier: str,
        display_name: str,
        timestamp: datetime,
    ) -> UpdateContactFromMessageResult:
        """Consume one message event idempotently and update its scoped Contact."""
        if not external_identifier or not external_identifier.strip():
            raise InvalidContactIdentityException("External identifier must not be empty.")

        with self._unit_of_work:
            if self._processed_messages.has_processed(event_id, self.CONSUMER_NAME):
                existing = self._contact_repository.find_by_external_identifier(
                    merchant_id,
                    platform_connection_id,
                    external_identifier,
                )
                if existing is None:
                    raise InvalidContactIdentityException(
                        "Processed message has no corresponding CRM contact."
                    )
                resolved = self._resolve_active_contact(existing)
                return UpdateContactFromMessageResult(resolved.id, False)

            contact = self._contact_repository.find_for_update_by_external_identifier(
                merchant_id,
                platform_connection_id,
                external_identifier,
            )
            if contact is not None:
                contact = self._resolve_active_contact(contact)
                contact.record_interaction(display_name, timestamp)
                self._contact_repository.save(contact)
                is_new_contact = False
            else:
                initial_contact = Contact.create(
                    merchant_id=merchant_id,
                    platform_connection_id=platform_connection_id,
                    external_identifier=external_identifier,
                    display_name=display_name,
                    initial_total_spent=self._defaults_provider.initial_total_spent(merchant_id),
                    occurred_at=timestamp,
                )
                contact, is_new_contact = self._contact_repository.get_or_create(initial_contact)
                if not is_new_contact:
                    contact = self._contact_repository.find_for_update_by_external_identifier(
                        merchant_id,
                        platform_connection_id,
                        external_identifier,
                    )
                    if contact is None:
                        raise InvalidContactIdentityException(
                            "Contact disappeared while processing its message event."
                        )
                    contact.record_interaction(display_name, timestamp)
                    self._contact_repository.save(contact)

            self._processed_messages.mark_processed(event_id, self.CONSUMER_NAME)

        return UpdateContactFromMessageResult(contact.id, is_new_contact)

    def _resolve_active_contact(self, contact: Contact) -> Contact:
        """Follow retained external-identity tombstones to their active Contact.

        Protects INV-CRM-07: messages addressed through a merged platform identity
        must never mutate the tombstone itself.
        """
        visited_contact_ids = {contact.id}
        current = contact
        while current.status is ContactStatus.MERGED:
            next_contact_id = current.merged_into_contact_id
            if next_contact_id is None or next_contact_id in visited_contact_ids:
                raise InvalidContactIdentityException(
                    "Merged contact redirection is invalid."
                )
            current = self._contact_repository.find_for_update_by_id(next_contact_id)
            if current is None or current.merchant_id != contact.merchant_id:
                raise InvalidContactIdentityException(
                    "Merged contact destination was not found."
                )
            visited_contact_ids.add(current.id)
        return current
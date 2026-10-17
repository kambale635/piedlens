from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ...domain.entities.contact import Contact
from ...domain.value_objects.contact_status import ContactStatus
from ...domain.exceptions.crm_exceptions import ContactAlreadyMergedException
from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.events.crm_events import ContactMerged, MergedContactSnapshot
from ..exceptions import ContactNotFoundException, ContactsMustBeDistinctException
from ..ports import ICRMOutbox, ICRMUnitOfWork


@dataclass(frozen=True)
class MergeContactsResult:
    """Synchronous result indicating that ContactMerged processing is underway."""

    primary_contact_id: UUID
    merged_contact_id: UUID
    status: str


class MergeContactsUseCase:
    """Tombstone one duplicate Contact and enqueue its immutable merge snapshot.

    This manually invoked merchant command implements only transaction one of the
    two-phase workflow. It reads and locks both Contacts in stable ID order to verify
    scope and state, but mutates only the duplicate Contact; its tombstone and the
    ContactMerged event commit together. CRM principal absorption and Order Detection
    reference reassignment run later in their own aggregate transactions.

    Contract: docs/15-use-cases-catalog.md#contexte-crm.

    Args:
        contact_repository: CRM-owned Contact lock/read/write port.
        unit_of_work: CRM transaction boundary for duplicate tombstone and Outbox.
        outbox: CRM producer Outbox sharing the active UnitOfWork.

    Returns:
        Primary and tombstone IDs with status `merge_in_progress`.

    Raises:
        ContactsMustBeDistinctException: if both IDs name the same Contact.
        ContactNotFoundException: if either Contact is absent or outside merchant scope.
        ContactAlreadyMergedException: if either Contact already has tombstone status.

    Protects INV-CRM-03, INV-CRM-07, and INV-TR-01/02.
    """

    def __init__(
        self,
        contact_repository: IContactRepository,
        unit_of_work: ICRMUnitOfWork,
        outbox: ICRMOutbox,
    ) -> None:
        """Receive the CRM persistence, transaction, and Outbox ports."""
        self._contact_repository = contact_repository
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(
        self,
        primary_contact_id: UUID,
        duplicate_contact_id: UUID,
        merchant_id: UUID,
    ) -> MergeContactsResult:
        """Mark only the duplicate as merged and publish its snapshot atomically."""
        if primary_contact_id == duplicate_contact_id:
            raise ContactsMustBeDistinctException("Contacts must be distinct.")

        with self._unit_of_work:
            locked_contacts: dict[UUID, Contact] = {}
            for contact_id in sorted(
                (primary_contact_id, duplicate_contact_id), key=str
            ):
                contact = self._contact_repository.find_for_update_by_id(contact_id)
                if contact is not None:
                    locked_contacts[contact_id] = contact

            primary = locked_contacts.get(primary_contact_id)
            duplicate = locked_contacts.get(duplicate_contact_id)
            if (
                primary is None
                or duplicate is None
                or primary.merchant_id != merchant_id
                or duplicate.merchant_id != merchant_id
            ):
                raise ContactNotFoundException("Contact was not found.")
            if primary.status is ContactStatus.MERGED:
                raise ContactAlreadyMergedException("Primary contact is already merged.")

            duplicate.mark_merged(primary_contact_id)
            self._contact_repository.save(duplicate)
            now = datetime.now(timezone.utc)
            self._outbox.add(
                ContactMerged(
                    event_id=uuid4(),
                    occurred_at=now,
                    merchant_id=merchant_id,
                    primary_contact_id=primary_contact_id,
                    merged_contact_id=duplicate_contact_id,
                    snapshot=MergedContactSnapshot(
                        total_spent_by_currency=duplicate.total_spent_by_currency,
                        order_count=duplicate.order_count,
                        purchase_history=duplicate.purchase_history,
                        tags=duplicate.tags,
                    ),
                )
            )

        return MergeContactsResult(
            primary_contact_id=primary_contact_id,
            merged_contact_id=duplicate_contact_id,
            status="merge_in_progress",
        )
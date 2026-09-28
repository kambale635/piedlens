from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from shared_kernel.value_objects.money import Money

from .loyalty_score import LoyaltyScore
from .purchase_history_entry import PurchaseHistoryEntry
from .contact_status import ContactStatus
from .exceptions import ContactAlreadyMergedException


@dataclass
class Contact:
    """Represents one platform customer within a merchant connection.

    Contact is the CRM Aggregate Root. Identity is `(merchant_id,
    platform_connection_id, external_identifier)`, never display name (INV-CRM-01).
    `total_spent` and `order_count` are not changed by message events (INV-CRM-04).
    Delivered purchase dates are retained as CRM-owned history entries (INV-CRM-04).
    """

    id: UUID
    merchant_id: UUID
    platform_connection_id: UUID
    external_identifier: str
    display_name: str
    total_spent_by_currency: tuple[Money, ...]
    order_count: int
    last_interaction_at: datetime
    loyalty_score: LoyaltyScore
    tags: tuple[str, ...]
    purchase_history: tuple[PurchaseHistoryEntry, ...] = ()
    status: ContactStatus = ContactStatus.ACTIVE
    merged_into_contact_id: UUID | None = None

    @classmethod
    def create(
        cls,
        merchant_id: UUID,
        platform_connection_id: UUID,
        external_identifier: str,
        display_name: str,
        initial_total_spent: Money,
        occurred_at: datetime,
    ) -> "Contact":
        """Create a new contact with configuration-provided currency defaults."""
        return cls(
            id=uuid4(),
            merchant_id=merchant_id,
            platform_connection_id=platform_connection_id,
            external_identifier=external_identifier,
            display_name=display_name,
            total_spent_by_currency=(initial_total_spent,),
            order_count=0,
            last_interaction_at=occurred_at,
            loyalty_score=LoyaltyScore(0),
            tags=(),
        )

    def record_interaction(self, display_name: str, occurred_at: datetime) -> None:
        """Apply only current/newer platform profile data without altering order totals.

        Protects INV-CRM-01 and INV-CRM-04: display name never determines identity,
        and message processing cannot update purchase aggregates.
        """
        if occurred_at >= self.last_interaction_at:
            self.display_name = display_name
            self.last_interaction_at = occurred_at

    def record_paid_order(
        self,
        order_id: UUID,
        order_amount: Money,
        purchased_at: datetime,
    ) -> bool:
        """Record one delivered order and its CRM-owned date exactly once.

        This method is called only by the OrderStatusChanged consumer after the
        event declares `paid_and_delivered`. The event timestamp and order identity
        are retained locally in CRM; no Order Detection repository is queried.
        Values are added within their currency using Money.add(), preserving
        INV-CRM-04, INV-OD-05, and INV-TR-05.

        Returns:
            True if this order was newly recorded; False if its order id is already
            present in this Contact's history.
        """
        if any(entry.order_id == order_id for entry in self.purchase_history):
            return False

        totals = {money.currency: money for money in self.total_spent_by_currency}
        existing_total = totals.get(order_amount.currency)
        totals[order_amount.currency] = (
            existing_total.add(order_amount) if existing_total else order_amount
        )
        self.total_spent_by_currency = tuple(totals[currency] for currency in sorted(totals))
        self.order_count += 1
        self.purchase_history = tuple(
            sorted(
                (*self.purchase_history, PurchaseHistoryEntry(order_id, purchased_at)),
                key=lambda entry: (entry.purchased_at, str(entry.order_id)),
            )
        )
        return True

    def update_loyalty_score(self, loyalty_score: LoyaltyScore) -> None:
        """Apply a score computed by the dedicated CRM domain service."""
        self.loyalty_score = loyalty_score

    def mark_merged(self, primary_contact_id: UUID) -> None:
        """Turn this Contact into a durable tombstone without deleting its audit data.

        Protects INV-CRM-07: a merged Contact is immutable as a business identity
        and redirects its external identifier to a distinct active primary Contact.
        """
        if self.status is ContactStatus.MERGED:
            raise ContactAlreadyMergedException("Contact has already been merged.")
        if primary_contact_id == self.id:
            raise ValueError("A Contact cannot be merged into itself.")
        self.status = ContactStatus.MERGED
        self.merged_into_contact_id = primary_contact_id
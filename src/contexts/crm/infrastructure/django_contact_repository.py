"""Module: contexts/crm/infrastructure/django_contact_repository.py
Context: CRM.
Role: map Contact aggregates to the CRM-owned PostgreSQL records.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django.db import IntegrityError
from shared_kernel.value_objects.money import Money

from ..domain.contact import Contact
from ..domain.contact_status import ContactStatus
from ..domain.i_contact_repository import IContactRepository
from ..domain.loyalty_score import LoyaltyScore
from ..domain.purchase_history_entry import PurchaseHistoryEntry
from .models import ContactRecord


class DjangoContactRepository(IContactRepository):
    """Persist CRM contacts with a database-enforced platform identity key."""

    def find_by_external_identifier(
        self,
        merchant_id: UUID,
        platform_connection_id: UUID,
        external_identifier: str,
    ) -> Contact | None:
        """Load by merchant/connection/external identifier; display name is never searched."""
        record = ContactRecord.objects.filter(
            merchant_id=merchant_id,
            platform_connection_id=platform_connection_id,
            external_identifier=external_identifier,
        ).first()
        return self._to_domain(record) if record else None

    def find_for_update_by_external_identifier(
        self,
        merchant_id: UUID,
        platform_connection_id: UUID,
        external_identifier: str,
    ) -> Contact | None:
        """Lock the Contact row until the CRM UnitOfWork commits."""
        record = (
            ContactRecord.objects.select_for_update()
            .filter(
                merchant_id=merchant_id,
                platform_connection_id=platform_connection_id,
                external_identifier=external_identifier,
            )
            .first()
        )
        return self._to_domain(record) if record else None

    def find_for_update_by_id(self, contact_id: UUID) -> Contact | None:
        """Lock and rehydrate one Contact row for a delivered-order update."""
        record = ContactRecord.objects.select_for_update().filter(id=contact_id).first()
        return self._to_domain(record) if record else None

    def find_by_merchant(self, merchant_id: UUID) -> list[Contact]:
        """List CRM-owned Contacts for scheduled merchant-scoped jobs."""
        records = ContactRecord.objects.filter(merchant_id=merchant_id).order_by("id")
        return [self._to_domain(record) for record in records]

    def get_or_create(self, contact: Contact) -> tuple[Contact, bool]:
        """Create by identity key atomically or rehydrate the winning concurrent insert."""
        try:
            record, created = ContactRecord.objects.get_or_create(
                merchant_id=contact.merchant_id,
                platform_connection_id=contact.platform_connection_id,
                external_identifier=contact.external_identifier,
                defaults=self._defaults(contact),
            )
        except IntegrityError:
            record = ContactRecord.objects.filter(
                merchant_id=contact.merchant_id,
                platform_connection_id=contact.platform_connection_id,
                external_identifier=contact.external_identifier,
            ).first()
            if record is None:
                raise
            created = False
        return self._to_domain(record), created

    def save(self, contact: Contact) -> None:
        """Persist the Contact aggregate without changing purchase totals here."""
        ContactRecord.objects.update_or_create(
            id=contact.id,
            defaults=self._defaults(contact),
        )

    @staticmethod
    def _defaults(contact: Contact) -> dict:
        return {
            "id": contact.id,
            "merchant_id": contact.merchant_id,
            "platform_connection_id": contact.platform_connection_id,
            "external_identifier": contact.external_identifier,
            "display_name": contact.display_name,
            "total_spent_by_currency": {
                money.currency: str(money.amount)
                for money in contact.total_spent_by_currency
            },
            "order_count": contact.order_count,
            "last_interaction_at": contact.last_interaction_at,
            "purchase_history": [
                {
                    "order_id": str(entry.order_id),
                    "purchased_at": entry.purchased_at.isoformat(),
                }
                for entry in contact.purchase_history
            ],
            "loyalty_score": contact.loyalty_score.value,
            "tags": list(contact.tags),
            "status": contact.status.value,
            "merged_into_contact_id": contact.merged_into_contact_id,
        }

    @staticmethod
    def _to_domain(record: ContactRecord) -> Contact:
        return Contact(
            id=record.id,
            merchant_id=record.merchant_id,
            platform_connection_id=record.platform_connection_id,
            external_identifier=record.external_identifier,
            display_name=record.display_name,
            total_spent_by_currency=tuple(
                Money(Decimal(amount), currency)
                for currency, amount in sorted(record.total_spent_by_currency.items())
            ),
            order_count=record.order_count,
            last_interaction_at=record.last_interaction_at,
            loyalty_score=LoyaltyScore(record.loyalty_score),
            tags=tuple(record.tags),
            purchase_history=tuple(
                PurchaseHistoryEntry(
                    order_id=UUID(entry["order_id"]),
                    purchased_at=datetime.fromisoformat(entry["purchased_at"]),
                )
                for entry in record.purchase_history
            ),
            status=ContactStatus(record.status),
            merged_into_contact_id=record.merged_into_contact_id,
        )
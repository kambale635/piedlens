"""Module: contexts/order_detection/infrastructure/django_contact_reference_redirect_repository.py
Context: Order Detection.
Role: persist this context's local projection of CRM Contact merge redirects.
"""

from uuid import UUID

from ...application.ports.i_contact_reference_redirect_repository import (
    IContactReferenceRedirectRepository,
)
from .models import ContactReferenceRedirectRecord


class DjangoContactReferenceRedirectRepository(IContactReferenceRedirectRepository):
    """Store and resolve CRM merge aliases without querying CRM tables."""

    def register(
        self,
        merchant_id: UUID,
        merged_contact_id: UUID,
        primary_contact_id: UUID,
    ) -> None:
        """Persist the redirect once; reject contradictory mappings for a tombstone."""
        record, created = ContactReferenceRedirectRecord.objects.get_or_create(
            merged_contact_id=merged_contact_id,
            defaults={
                "merchant_id": merchant_id,
                "primary_contact_id": primary_contact_id,
            },
        )
        if not created and (
            record.merchant_id != merchant_id
            or record.primary_contact_id != primary_contact_id
        ):
            raise ValueError("Conflicting Contact merge redirect received.")

    def resolve(self, merchant_id: UUID, contact_id: UUID) -> UUID:
        """Follow the local redirect chain to its latest known primary Contact."""
        current_id = contact_id
        visited_ids = set()
        while current_id not in visited_ids:
            visited_ids.add(current_id)
            redirect = ContactReferenceRedirectRecord.objects.filter(
                merchant_id=merchant_id,
                merged_contact_id=current_id,
            ).first()
            if redirect is None:
                return current_id
            current_id = redirect.primary_contact_id
        raise ValueError("Contact merge redirect cycle detected.")
import re
from urllib.parse import quote
from uuid import UUID

from shared_kernel.application_exceptions import ValidationException

from ..persistence.django_contact_repository import DjangoContactRepository


class InvalidManualLinkRecipientException(ValidationException):
    error_code = "MANUAL_LINK_RECIPIENT_UNAVAILABLE"


class DjangoManualMessageLinkBuilder:
    """Build a wa.me link only from a tenant-owned Contact with an E.164-style identifier."""

    def __init__(self, contacts=None) -> None:
        self._contacts = contacts or DjangoContactRepository()

    def create_link(self, merchant_id: UUID, contact_id: UUID, content: str) -> str:
        contact = self._contacts.find_by_id(contact_id)
        if (
            contact is None
            or contact.merchant_id != merchant_id
            or not re.fullmatch(r"[1-9][0-9]{7,14}", contact.external_identifier)
        ):
            raise InvalidManualLinkRecipientException(
                "Contact has no international phone number usable for a WhatsApp link."
            )
        return f"https://wa.me/{contact.external_identifier}?text={quote(content)}"
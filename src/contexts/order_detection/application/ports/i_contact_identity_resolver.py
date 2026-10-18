from datetime import datetime
from typing import Protocol
from uuid import UUID


class IContactIdentityResolver(Protocol):
    """Resolve or create a CRM Contact through an explicit application boundary."""

    def resolve_or_create(
        self,
        event_id: UUID,
        merchant_id: UUID,
        platform_connection_id: UUID,
        external_sender_id: str,
        display_name: str,
        received_at: datetime,
    ) -> UUID: ...
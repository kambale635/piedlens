from typing import Protocol
from uuid import UUID


class IManualMessageLinkBuilder(Protocol):
    """Build a local, prefilled messaging link without calling an external API."""

    def create_link(self, merchant_id: UUID, contact_id: UUID, content: str) -> str: ...
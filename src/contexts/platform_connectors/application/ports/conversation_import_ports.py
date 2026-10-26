from typing import Protocol
from uuid import UUID


class IImportFormatReader(Protocol):
    """Read active, versioned manual import format configuration (INV-IMP-04)."""

    def find_active(self, code: str) -> dict | None: ...


class IConversationImportRepository(Protocol):
    """Persist consented import jobs and expose merchant-scoped status (INV-IMP-01/02)."""

    def create_if_new(self, values: dict) -> tuple[UUID, bool]: ...

    def status_for_merchant(self, import_id: UUID, merchant_id: UUID) -> dict | None: ...

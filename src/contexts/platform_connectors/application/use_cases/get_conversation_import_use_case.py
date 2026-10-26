from uuid import UUID

from shared_kernel.application_exceptions import ResourceNotFoundException


class GetConversationImportUseCase:
    """Return import progress only to its owning merchant (INV-IMP-01/04)."""

    def __init__(self, imports):
        self._imports = imports

    def execute(self, merchant_id: UUID, import_id: UUID) -> dict:
        """Read a merchant-scoped import status without returning source content."""
        result = self._imports.status_for_merchant(import_id, merchant_id)
        if result is None:
            raise ResourceNotFoundException("Conversation import was not found.")
        return result

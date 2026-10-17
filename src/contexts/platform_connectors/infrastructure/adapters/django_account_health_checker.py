from uuid import UUID

from ...domain.value_objects.connection_status import ConnectionStatus
from ..persistence.models import PlatformConnectionRecord


class DjangoAccountHealthChecker:
    """Provide a local health signal from stored connection state until provider APIs are wired."""

    def check_account_status(self, connection_id: UUID) -> tuple[str, list[str]]:
        """Translate connection lifecycle state without accessing external provider APIs."""
        status = PlatformConnectionRecord.objects.filter(id=connection_id).values_list(
            "status", flat=True
        ).first()
        if status is None:
            return "suspended", ["connection_not_found"]
        if status == ConnectionStatus.ACTIVE.value:
            return "healthy", []
        return "suspended", ["connection_not_active"]
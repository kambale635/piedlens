from uuid import UUID

from ...domain.value_objects.connection_status import ConnectionStatus
from ..persistence.models import PlatformConnectionRecord


class DjangoConnectionUsageReader:
    """Implement the shared usage query over Platform Connectors-owned records."""

    def count_active_connections(self, merchant_id: UUID) -> int:
        """Count active connections used by a merchant (INV-ID-03)."""
        return PlatformConnectionRecord.objects.filter(
            merchant_id=merchant_id,
            status=ConnectionStatus.ACTIVE.value,
        ).count()
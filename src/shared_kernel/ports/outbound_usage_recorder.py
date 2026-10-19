from typing import Protocol
from uuid import UUID


class IOutboundUsageRecorder(Protocol):
    """Atomically reserve API outbound usage against the merchant's monthly entitlement."""

    def reserve(
        self, merchant_id: UUID, category: str, idempotency_key: str
    ) -> dict[str, object]: ...

    def usage_for(self, merchant_id: UUID) -> list[dict[str, object]]: ...
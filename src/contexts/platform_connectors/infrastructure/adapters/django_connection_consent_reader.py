from uuid import UUID

from ..persistence.models import PlatformConnectionRecord


class DjangoConnectionConsentReader:
    """Expose only merchant and consent metadata through a shared-kernel port (INV-BK-03)."""

    def consent_for(self, connection_id: UUID) -> tuple[UUID, object | None] | None:
        """Return the connection owner and explicit consent timestamp, if present."""
        row = PlatformConnectionRecord.objects.filter(id=connection_id).values_list(
            "merchant_id", "consent_given_at"
        ).first()
        return row if row is not None else None
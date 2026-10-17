from uuid import UUID

from ...domain.entities.platform_connection import PlatformConnection
from ...domain.value_objects.connection_status import ConnectionStatus
from ...domain.value_objects.encrypted_token import EncryptedToken
from ...domain.value_objects.platform_type import PlatformType
from .models import PlatformConnectionRecord


class DjangoPlatformConnectionRepository:
    """Persist connector aggregates without exposing the ORM to application code."""

    def find_by_id(self, connection_id: UUID) -> PlatformConnection | None:
        """Load a connection by its opaque public identifier."""
        record = PlatformConnectionRecord.objects.filter(id=connection_id).first()
        return self._to_domain(record) if record else None

    def find_active_by_merchant(self, merchant_id: UUID) -> list[PlatformConnection]:
        """Return active connections in stable order for a merchant-scoped job."""
        records = PlatformConnectionRecord.objects.filter(
            merchant_id=merchant_id,
            status=ConnectionStatus.ACTIVE.value,
        ).order_by("id")
        return [self._to_domain(record) for record in records]

    def save(self, connection: PlatformConnection) -> None:
        """Persist the opaque credential and aggregate state only."""
        PlatformConnectionRecord.objects.update_or_create(
            id=connection.id,
            defaults={
                "merchant_id": connection.merchant_id,
                "platform_type": connection.platform_type.value,
                "external_account_id": connection.external_account_id,
                "encrypted_access_token": connection.encrypted_access_token.value,
                "status": connection.status.value,
                "consent_given_at": connection.consent_given_at,
                "last_synced_at": connection.last_synced_at,
            },
        )

    @staticmethod
    def _to_domain(record: PlatformConnectionRecord) -> PlatformConnection:
        """Rehydrate the aggregate while keeping token contents opaque."""
        return PlatformConnection(
            id=record.id,
            merchant_id=record.merchant_id,
            platform_type=PlatformType(record.platform_type),
            external_account_id=record.external_account_id,
            encrypted_access_token=EncryptedToken(record.encrypted_access_token),
            status=ConnectionStatus(record.status),
            consent_given_at=record.consent_given_at,
            last_synced_at=record.last_synced_at,
        )
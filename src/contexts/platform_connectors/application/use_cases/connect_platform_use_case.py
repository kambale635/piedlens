from uuid import uuid4

from shared_kernel.domain_exceptions import DomainException
from shared_kernel.ports import IConnectionPlanReader, IConnectionUsageReader

from ...domain.entities.platform_connection import PlatformConnection
from ...domain.events.platform_events import PlatformConnected
from ...domain.value_objects.connection_status import ConnectionStatus
from ...domain.value_objects.platform_type import PlatformType
from ..exceptions import InvalidOAuthCodeException, PlanConnectionLimitReachedException
from ..ports.platform_ports import (
    IPlatformClock,
    IPlatformConnectorsOutbox,
    IPlatformConnectorsUnitOfWork,
    IPlatformConnectionRepository,
    IPlatformGateway,
    ITokenCipher,
)


class ConnectPlatformUseCase:
    """Connect a merchant account using the injected platform gateway and encrypted token.

    Contract: docs/15-use-cases-catalog.md#contexte-platform-connectors.
    Checks plan capacity before creating a connection (INV-ID-01) and stores only an
    encrypted access token (INV-PC-01). Consent is recorded only when explicitly granted.
    """

    def __init__(
        self,
        connections: IPlatformConnectionRepository,
        gateway: IPlatformGateway,
        cipher: ITokenCipher,
        usage_reader: IConnectionUsageReader,
        plan_reader: IConnectionPlanReader,
        unit_of_work: IPlatformConnectorsUnitOfWork,
        outbox: IPlatformConnectorsOutbox,
        clock: IPlatformClock,
    ) -> None:
        """Receive provider, persistence, plan and transaction adapters through ports."""
        self._connections = connections
        self._gateway = gateway
        self._cipher = cipher
        self._usage_reader = usage_reader
        self._plan_reader = plan_reader
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(
        self,
        merchant_id,
        platform_type: str,
        oauth_code: str,
        external_account_id: str | None = None,
        consent_given: bool = False,
    ) -> dict:
        """Persist one active connection and its event after validating plan capacity."""
        try:
            normalized_platform = PlatformType(platform_type)
        except ValueError as error:
            raise InvalidOAuthCodeException("Unsupported platform type.") from error

        limit = self._plan_reader.active_connection_limit(merchant_id)
        usage = self._usage_reader.count_active_connections(merchant_id)
        if limit is not None and usage >= limit:
            raise PlanConnectionLimitReachedException("Plan connection limit reached.")

        token, resolved_account_id = self._gateway.exchange_oauth_code(
            normalized_platform.value, oauth_code, external_account_id
        )
        if not token or not resolved_account_id:
            raise InvalidOAuthCodeException("OAuth code could not be exchanged.")

        now = self._clock.now_utc()
        connection = PlatformConnection(
            id=uuid4(),
            merchant_id=merchant_id,
            platform_type=normalized_platform,
            external_account_id=resolved_account_id,
            encrypted_access_token=self._cipher.encrypt(token),
            status=ConnectionStatus.ACTIVE,
            consent_given_at=now if consent_given else None,
        )
        with self._unit_of_work:
            self._connections.save(connection)
            self._outbox.add(
                PlatformConnected(
                    merchant_id=merchant_id,
                    connection_id=connection.id,
                    platform_type=normalized_platform.value,
                    occurred_at=now,
                )
            )
        return {"platform_connection_id": connection.id, "connection_status": "active"}
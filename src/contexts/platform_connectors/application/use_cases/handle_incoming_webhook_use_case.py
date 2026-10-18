import json
from uuid import UUID

from shared_kernel.application_exceptions import ValidationException

from ...domain.events.platform_events import MessageReceived
from ..exceptions import InvalidWebhookSignatureException, PlatformConnectionNotFoundException
from ..ports.channel_capabilities import IWebhookMessageNormalizer, IWebhookSignatureVerifier
from ..ports.channel_provider_registry import IChannelProviderRegistry
from ..ports.platform_ports import (
    IMessageRepository,
    IPlatformConnectorsOutbox,
    IPlatformConnectorsUnitOfWork,
    IPlatformConnectionRepository,
)


class HandleIncomingWebhookUseCase:
    """Verify a webhook signature before parsing, then persist normalized messages idempotently.

    Contract: docs/15-use-cases-catalog.md#contexte-platform-connectors.
    Invalid signatures are rejected before payload access (INV-PC-02); repeated external
    message IDs create neither a second row nor a second event (INV-PC-03, INV-TR-02).
    """

    def __init__(
        self,
        connections: IPlatformConnectionRepository,
        messages: IMessageRepository,
        providers: IChannelProviderRegistry,
        unit_of_work: IPlatformConnectorsUnitOfWork,
        outbox: IPlatformConnectorsOutbox,
    ) -> None:
        """Receive signature, ACL, persistence and Outbox ports through injection."""
        self._connections = connections
        self._messages = messages
        self._providers = providers
        self._unit_of_work = unit_of_work
        self._outbox = outbox

    def execute(self, platform_type: str, raw_body: bytes, signature: str) -> dict:
        """Reject unsigned payloads before decoding or persisting any content (INV-PC-02)."""
        verifier = self._providers.require(platform_type, IWebhookSignatureVerifier)
        if not verifier.verify(platform_type, raw_body, signature):
            raise InvalidWebhookSignatureException("Webhook signature is invalid.")
        try:
            payload = json.loads(raw_body)
            connection_id = UUID(str(payload["platformConnectionId"]))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            raise ValidationException("Webhook payload is malformed.") from error

        connection = self._connections.find_by_id(connection_id)
        if connection is None or connection.platform_type.value != platform_type:
            raise PlatformConnectionNotFoundException("Platform connection was not found.")

        normalizer = self._providers.require(platform_type, IWebhookMessageNormalizer)
        mapped_messages = normalizer.normalize(connection, payload)
        accepted_count = 0
        with self._unit_of_work:
            for message in mapped_messages:
                if self._messages.save_if_new(message):
                    accepted_count += 1
                    self._outbox.add(
                        MessageReceived(
                            merchant_id=message.merchant_id,
                            platform_connection_id=message.platform_connection_id,
                            message_id=message.id,
                            external_message_id=message.external_message_id,
                            external_sender_id=message.external_sender_id,
                            display_name=message.display_name,
                            text_content=message.text_content,
                            received_at=message.received_at,
                        )
                    )
        return {"accepted_count": accepted_count}
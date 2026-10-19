from dataclasses import dataclass

from ...application.ports.channel_capabilities import IMessageSender
from ...application.services.channel_provider_registry import (
    ChannelCapabilityUnavailableException,
)
from ...infrastructure.persistence.django_platform_connection_repository import (
    DjangoPlatformConnectionRepository,
)


@dataclass(frozen=True)
class CampaignDeliveryResult:
    succeeded: bool
    failure_code: str | None = None


class PlatformCampaignSender:
    """Deliver CRM recipients through registered Platform Connectors capabilities."""

    def __init__(self, providers, connections=None) -> None:
        self._providers = providers
        self._connections = connections or DjangoPlatformConnectionRepository()

    def send_message(self, channel, contact, template, idempotency_key):
        connection = self._connections.find_by_id(contact.platform_connection_id)
        if connection is None or connection.merchant_id != contact.merchant_id:
            return CampaignDeliveryResult(False, "CONNECTION_NOT_FOUND")
        try:
            sender = self._providers.require(channel, IMessageSender)
        except ChannelCapabilityUnavailableException:
            return CampaignDeliveryResult(False, "CHANNEL_UNAVAILABLE")
        result = sender.send_message(
            connection,
            contact.external_identifier,
            template,
            idempotency_key,
        )
        return CampaignDeliveryResult(
            result.get("status") == "sent", result.get("failureCode")
        )
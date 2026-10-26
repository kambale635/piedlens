import unittest

from django.test import SimpleTestCase

from contexts.platform_connectors.application.ports.channel_capabilities import (
    IChannelHealthChecker,
    IMediaFetcher,
    IMessageRetriever,
    IMessageSender,
    IOAuthCodeExchanger,
    ITokenRefresher,
    IWebhookMessageNormalizer,
    IWebhookSignatureVerifier,
)
from contexts.platform_connectors.application.services.channel_provider_registry import (
    ChannelCapabilityUnavailableException,
    ChannelProviderRegistry,
)
from contexts.platform_connectors.infrastructure.adapters.mock_channel_capabilities import (
    MockChannelHealthChecker,
    MockMediaFetcher,
    MockMessageRetriever,
    MockMessageSender,
    MockOAuthCodeExchanger,
    MockTokenRefresher,
)
from contexts.platform_connectors.infrastructure.adapters.mock_webhook_payload_mapper import (
    MockWebhookPayloadMapper,
)


CAPABILITY_METHODS = {
    IOAuthCodeExchanger: ("exchange_oauth_code",),
    IMessageRetriever: ("fetch_messages",),
    IMessageSender: ("send_message",),
    IMediaFetcher: ("download_media",),
    IChannelHealthChecker: ("check_connection",),
    IWebhookSignatureVerifier: ("verify",),
    ITokenRefresher: ("refresh_access_token",),
    IWebhookMessageNormalizer: ("normalize",),
}


class ChannelProviderContractMixin:
    """Reusable contract tests for any channel adapter registry and its declared capabilities."""

    channel_code = "contract_channel"
    supported_capabilities = frozenset(CAPABILITY_METHODS)

    def build_registry(self):
        raise NotImplementedError

    def test_each_declared_capability_implements_its_contract(self):
        registry = self.build_registry()

        for capability in self.supported_capabilities:
            adapter = registry.require(self.channel_code, capability)
            for method_name in CAPABILITY_METHODS[capability]:
                with self.subTest(capability=capability.__name__, method=method_name):
                    self.assertTrue(callable(getattr(adapter, method_name, None)))


class MockChannelProviderContractTests(ChannelProviderContractMixin, SimpleTestCase):
    def build_registry(self):
        class MockVerifier:
            def verify(self, channel_code, raw_body, signature):
                return bool(signature)

        return ChannelProviderRegistry(
            {
                self.channel_code: {
                    IOAuthCodeExchanger: MockOAuthCodeExchanger(),
                    IMessageRetriever: MockMessageRetriever(),
                    IMessageSender: MockMessageSender(),
                    IMediaFetcher: MockMediaFetcher(),
                    IChannelHealthChecker: MockChannelHealthChecker(),
                    IWebhookSignatureVerifier: MockVerifier(),
                    ITokenRefresher: MockTokenRefresher(),
                    IWebhookMessageNormalizer: MockWebhookPayloadMapper(),
                }
            }
        )

    def test_registry_does_not_fake_an_unsupported_capability(self):
        registry = ChannelProviderRegistry(
            {"read_only": {IMessageRetriever: MockMessageRetriever()}}
        )

        with self.assertRaises(ChannelCapabilityUnavailableException):
            registry.require("read_only", IMessageSender)

    def test_new_fake_channel_registers_at_runtime_without_existing_code_changes(self):
        class FakeConversationSource:
            def normalize(self, connection, payload):
                return payload["messages"]

        registry = ChannelProviderRegistry(
            {"fake_channel": {IWebhookMessageNormalizer: FakeConversationSource()}}
        )
        self.assertEqual(
            registry.require("fake_channel", IWebhookMessageNormalizer).normalize(
                None, {"messages": ["normalized"]}
            ),
            ["normalized"],
        )
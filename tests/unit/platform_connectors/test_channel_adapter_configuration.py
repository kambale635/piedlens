from django.test import SimpleTestCase, override_settings

from contexts.platform_connectors.application.ports.channel_capabilities import IMessageRetriever
from piedlens_platform.di.container import ApplicationContainer


class ChannelAdapterConfigurationTests(SimpleTestCase):
    @override_settings(PLATFORM_ADAPTERS={})
    def test_unconfigured_channels_use_mock_capabilities(self):
        registry = ApplicationContainer.channel_provider_registry()

        self.assertTrue(callable(registry.require("whatsapp", IMessageRetriever).fetch_messages))
        self.assertTrue(callable(registry.require("instagram", IMessageRetriever).fetch_messages))
        self.assertTrue(callable(registry.require("facebook", IMessageRetriever).fetch_messages))

    @override_settings(PLATFORM_ADAPTERS={"instagram": "real"})
    def test_real_mode_fails_clearly_without_a_real_adapter(self):
        with self.assertRaisesRegex(RuntimeError, "INSTAGRAM_ADAPTER=real cannot be used yet"):
            ApplicationContainer.channel_provider_registry()

    @override_settings(PLATFORM_ADAPTERS={"facebook": "unexpected"})
    def test_unknown_adapter_mode_fails_clearly(self):
        with self.assertRaisesRegex(RuntimeError, "Unsupported facebook adapter"):
            ApplicationContainer.channel_provider_registry()
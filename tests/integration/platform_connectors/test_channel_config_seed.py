from django.test import TestCase

from contexts.platform_connectors.infrastructure.persistence.models import ChannelConfigRecord


class ChannelConfigSeedTests(TestCase):
    def test_supported_mock_channels_have_deterministic_default_configuration(self):
        configs = {
            config.code: config
            for config in ChannelConfigRecord.objects.filter(
                code__in=("whatsapp", "instagram", "facebook")
            )
        }

        self.assertEqual(set(configs), {"whatsapp", "instagram", "facebook"})
        for config in configs.values():
            with self.subTest(channel=config.code):
                self.assertTrue(config.active)
                self.assertEqual(
                    config.plan_flags,
                    {"starter": True, "pro": True, "agency": True},
                )
                self.assertEqual(config.country_flags, {})
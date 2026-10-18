from uuid import uuid4

from django.core.cache import cache
from django.test import SimpleTestCase

from contexts.platform_connectors.infrastructure.adapters.django_webhook_replay_cache import (
    DjangoWebhookReplayCache,
)


class WebhookReplayCacheTests(SimpleTestCase):
    def test_redis_accepts_only_the_first_claim_during_the_ttl(self):
        replay_cache = DjangoWebhookReplayCache()
        replay_key = str(uuid4())
        cache_key = replay_cache._cache_key("whatsapp", replay_key)

        try:
            self.assertTrue(replay_cache.claim("whatsapp", replay_key, 30))
            self.assertFalse(replay_cache.claim("whatsapp", replay_key, 30))
        finally:
            cache.delete(cache_key)
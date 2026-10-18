import hashlib

from django.core.cache import cache


class DjangoWebhookReplayCache:
    """Claim webhook fingerprints atomically through the configured Redis cache."""

    def __init__(self, cache_backend=None) -> None:
        self._cache = cache_backend if cache_backend is not None else cache

    def claim(self, channel_code: str, replay_key: str, ttl_seconds: int) -> bool:
        """Return true only for the first claim during the configured replay window."""
        if ttl_seconds < 1:
            raise ValueError("Webhook replay TTL must be positive.")
        return self._cache.add(
            self._cache_key(channel_code, replay_key),
            "1",
            timeout=ttl_seconds,
        )

    @staticmethod
    def _cache_key(channel_code: str, replay_key: str) -> str:
        digest = hashlib.sha256(replay_key.encode("utf-8")).hexdigest()
        return f"platform:webhook:replay:{channel_code}:{digest}"
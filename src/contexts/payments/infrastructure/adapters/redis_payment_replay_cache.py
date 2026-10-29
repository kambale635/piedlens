from django.conf import settings
import redis


class RedisPaymentReplayCache:
    """Claim verified provider event IDs in Redis with bounded expiry (INV-PAY-02/T7)."""

    def __init__(self, client=None):
        options = {}
        if settings.REDIS_TLS_CA_CERTS:
            options["ssl_ca_certs"] = settings.REDIS_TLS_CA_CERTS
            options["ssl_cert_reqs"] = "required"
        self._client = client or redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True, **options
        )

    def claim(self, provider_code: str, event_id: str, ttl_seconds: int) -> bool:
        return bool(self._client.set(f"payments:webhook:{provider_code}:{event_id}", "1", nx=True, ex=ttl_seconds))

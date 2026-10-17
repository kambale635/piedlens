"""Module: contexts/crm/infrastructure/redis_segment_membership_cache.py
Context: CRM.
Role: cache dynamic segment membership pages; PostgreSQL remains authoritative.
"""

import json
import logging
from uuid import UUID

try:
    from redis.exceptions import RedisError
except ImportError:
    class RedisError(Exception):
        """Fallback used only by isolated tests without the declared Redis package."""


logger = logging.getLogger(__name__)


class RedisSegmentMembershipCache:
    """Cache segment pages under a merchant version with bounded Redis TTL."""

    def __init__(self, redis_client, ttl_seconds: int) -> None:
        """Receive the Redis client and configured TTL from the composition root."""
        if isinstance(ttl_seconds, bool) or not 300 <= ttl_seconds <= 900:
            raise ValueError("Segment membership cache TTL must be between 300 and 900 seconds.")
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def get_members(
        self,
        segment_id: UUID,
        merchant_id: UUID,
        page: int,
        page_size: int,
    ) -> dict | None:
        """Return a cached page or a cache miss when Redis is unavailable."""
        try:
            version = self._version(merchant_id)
            value = self._redis.get(self._page_key(segment_id, merchant_id, version, page, page_size))
        except RedisError:
            logger.warning("CRM segment membership cache read failed.")
            return None
        if value is None:
            return None
        result = json.loads(value)
        for contact in result["contacts"]:
            contact["contact_id"] = UUID(contact["contact_id"])
        return result

    def set_members(
        self,
        segment_id: UUID,
        merchant_id: UUID,
        page: int,
        page_size: int,
        result: dict,
    ) -> None:
        """Store a JSON-safe page without making Redis a source of truth."""
        try:
            version = self._version(merchant_id)
            payload = json.dumps(
                result,
                default=lambda value: str(value) if isinstance(value, UUID) else value,
                separators=(",", ":"),
            )
            self._redis.set(
                self._page_key(segment_id, merchant_id, version, page, page_size),
                payload,
                ex=self._ttl_seconds,
            )
        except RedisError:
            logger.warning("CRM segment membership cache write failed.")

    def invalidate_merchant(self, merchant_id: UUID) -> None:
        """Advance the merchant cache namespace without scanning Redis keys."""
        try:
            self._redis.incr(self._version_key(merchant_id))
        except RedisError:
            logger.warning("CRM segment membership cache invalidation failed.")

    def _version(self, merchant_id: UUID) -> int:
        value = self._redis.get(self._version_key(merchant_id))
        return int(value or 0)

    @staticmethod
    def _version_key(merchant_id: UUID) -> str:
        return f"crm:segment-members:merchant:{merchant_id}:version"

    @staticmethod
    def _page_key(
        segment_id: UUID,
        merchant_id: UUID,
        version: int,
        page: int,
        page_size: int,
    ) -> str:
        return (
            f"crm:segment-members:merchant:{merchant_id}:version:{version}:"
            f"segment:{segment_id}:page:{page}:size:{page_size}"
        )
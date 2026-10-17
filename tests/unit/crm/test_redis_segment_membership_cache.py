import unittest
from uuid import uuid4

from contexts.crm.infrastructure.adapters.redis_segment_membership_cache import (
    RedisSegmentMembershipCache,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex):
        self.values[key] = value
        self.expirations[key] = ex

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]


class RedisSegmentMembershipCacheTests(unittest.TestCase):
    def test_rejects_ttl_outside_documented_range(self):
        with self.assertRaises(ValueError):
            RedisSegmentMembershipCache(redis_client=FakeRedis(), ttl_seconds=60)

    def test_serializes_uuid_and_invalidates_all_pages_by_advancing_version(self):
        redis_client = FakeRedis()
        cache = RedisSegmentMembershipCache(redis_client=redis_client, ttl_seconds=300)
        merchant_id = uuid4()
        segment_id = uuid4()
        contact_id = uuid4()
        page = {
            "contacts": [{"contact_id": contact_id, "display_name": "A"}],
            "total_count": 1,
        }

        cache.set_members(segment_id, merchant_id, 1, 25, page)
        loaded = cache.get_members(segment_id, merchant_id, 1, 25)

        self.assertEqual(loaded, page)
        self.assertEqual(next(iter(redis_client.expirations.values())), 300)

        cache.invalidate_merchant(merchant_id)

        self.assertIsNone(cache.get_members(segment_id, merchant_id, 1, 25))


if __name__ == "__main__":
    unittest.main()
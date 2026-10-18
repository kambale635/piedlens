import unittest

from django.test import override_settings

from contexts.identity.infrastructure.adapters.django_security_services import (
    DjangoLoginBackoff,
    DjangoPasswordHasher,
)


class FakeCache:
    def __init__(self):
        self.values = {}
        self.timeouts = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def add(self, key, value, timeout=None):
        if key in self.values:
            return False
        self.values[key] = value
        self.timeouts[key] = timeout
        return True

    def incr(self, key):
        if key not in self.values:
            raise ValueError("Key is missing")
        self.values[key] += 1
        return self.values[key]

    def set(self, key, value, timeout=None):
        self.values[key] = value
        self.timeouts[key] = timeout

    def delete_many(self, keys):
        for key in keys:
            self.values.pop(key, None)
            self.timeouts.pop(key, None)


class IdentityAuthSecurityTests(unittest.TestCase):
    def test_django_password_validators_reject_short_and_numeric_passwords(self):
        hasher = DjangoPasswordHasher()

        self.assertFalse(hasher.validate("short1"))
        self.assertFalse(hasher.validate("123456789012"))
        self.assertTrue(hasher.validate("correct-horse-battery-7"))

    @override_settings(
        IDENTITY_LOGIN_BACKOFF_BASE_SECONDS=2,
        IDENTITY_LOGIN_BACKOFF_MAX_SECONDS=10,
        IDENTITY_LOGIN_BACKOFF_WINDOW_SECONDS=60,
    )
    def test_login_backoff_progressively_increases_then_clears(self):
        cache = FakeCache()
        backoff = DjangoLoginBackoff(cache)
        attempt_key = "127.0.0.1:+14155550123"
        blocked_key = backoff._cache_key("blocked", attempt_key)

        self.assertFalse(backoff.is_blocked(attempt_key))
        backoff.record_failure(attempt_key)
        self.assertTrue(backoff.is_blocked(attempt_key))
        self.assertEqual(cache.timeouts[blocked_key], 2)

        cache.delete_many([blocked_key])
        backoff.record_failure(attempt_key)
        self.assertEqual(cache.timeouts[blocked_key], 4)
        cache.delete_many([blocked_key])
        backoff.record_failure(attempt_key)
        cache.delete_many([blocked_key])
        backoff.record_failure(attempt_key)
        self.assertEqual(cache.timeouts[blocked_key], 10)

        backoff.clear(attempt_key)
        self.assertFalse(backoff.is_blocked(attempt_key))


if __name__ == "__main__":
    unittest.main()
import hashlib
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.backup.application.exceptions import InvalidReauthenticationException
from contexts.backup.application.use_cases.request_merchant_deletion_use_case import (
    RequestMerchantDeletionUseCase,
)


class FakeReauthentication:
    def __init__(self, valid):
        self.valid = valid
        self.calls = []

    def verify(self, user_id, password):
        self.calls.append((user_id, password))
        return self.valid


class FakeTokens:
    def __init__(self):
        self.saved = []

    def save(self, merchant_id, user_id, token_hash, expires_at):
        self.saved.append((merchant_id, user_id, token_hash, expires_at))


class FakeClock:
    def now_utc(self):
        return datetime(2026, 10, 18, tzinfo=timezone.utc)


class RequestMerchantDeletionUseCaseTests(unittest.TestCase):
    def test_reauthentication_issues_only_a_hashed_fifteen_minute_token(self):
        merchant_id = uuid4()
        user_id = uuid4()
        tokens = FakeTokens()
        use_case = RequestMerchantDeletionUseCase(
            FakeReauthentication(True), tokens, FakeClock()
        )

        result = use_case.execute(merchant_id, user_id, "current-password")

        self.assertEqual(len(result["confirmation_token"]), 43)
        self.assertEqual(
            result["expires_at"],
            datetime(2026, 10, 18, 0, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(len(tokens.saved), 1)
        self.assertEqual(tokens.saved[0][0:2], (merchant_id, user_id))
        self.assertEqual(
            tokens.saved[0][2],
            hashlib.sha256(result["confirmation_token"].encode()).hexdigest(),
        )
        self.assertNotEqual(tokens.saved[0][2], result["confirmation_token"])

    def test_wrong_password_uses_catalogued_authentication_error_and_saves_nothing(self):
        tokens = FakeTokens()
        use_case = RequestMerchantDeletionUseCase(
            FakeReauthentication(False), tokens, FakeClock()
        )

        with self.assertRaises(InvalidReauthenticationException) as raised:
            use_case.execute(uuid4(), uuid4(), "wrong-password")

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.error_code, "INVALID_CREDENTIALS")
        self.assertEqual(tokens.saved, [])


if __name__ == "__main__":
    unittest.main()
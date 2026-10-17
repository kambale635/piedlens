import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.identity.application.exceptions.identity_exceptions import (
    InvalidCredentials,
    InvalidRefreshToken,
    PhoneAlreadyRegistered,
    WeakPassword,
)
from contexts.identity.application.use_cases.authenticate_user_use_case import (
    AuthenticateUserUseCase,
)
from contexts.identity.application.use_cases.change_subscription_plan_use_case import (
    ChangeSubscriptionPlanUseCase,
)
from contexts.identity.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from contexts.identity.application.use_cases.register_user_use_case import RegisterUserUseCase
from contexts.identity.domain.entities.merchant import DowngradeExceedsCurrentUsage, Merchant
from contexts.identity.domain.value_objects.identity_values import (
    CountryCode,
    CurrencyCode,
    LanguageCode,
    SubscriptionPlan,
)


class IdentityUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.users = FakeUsers()
        self.events = []
        self.use_case = RegisterUserUseCase(
            self.users,
            FakeHasher(),
            FakeUnitOfWork(),
            FakeOutbox(self.events),
            FakeClock(),
        )

    def test_registration_persists_hash_and_emits_event(self):
        result = self.use_case.execute("+14155550123", "long-password-123")
        user = self.users.by_phone["+14155550123"]
        self.assertEqual(result["userId"], user.id)
        self.assertNotEqual(user.password_hash, "long-password-123")
        self.assertEqual(len(self.events), 1)

    def test_registration_rejects_duplicate_phone_and_weak_password(self):
        self.use_case.execute("+14155550123", "long-password-123")
        with self.assertRaises(PhoneAlreadyRegistered):
            self.use_case.execute("+14155550123", "another-password-123")
        with self.assertRaises(WeakPassword):
            self.use_case.execute("+14155550124", "short1")

    def test_missing_user_and_wrong_password_share_error(self):
        authenticate = AuthenticateUserUseCase(self.users, FakeHasher(), FakeTokens())
        with self.assertRaises(InvalidCredentials) as missing:
            authenticate.execute("+14155550124", "wrong-password-123")
        self.use_case.execute("+14155550123", "correct-password-123")
        with self.assertRaises(InvalidCredentials) as wrong:
            authenticate.execute("+14155550123", "wrong-password-123")
        self.assertEqual(missing.exception.error_code, wrong.exception.error_code)
        self.assertEqual(missing.exception.status_code, wrong.exception.status_code)

    def test_plan_downgrade_rejects_usage_above_target_limit(self):
        merchant = Merchant.register(
            uuid4(), "Shop", CountryCode("FR"), LanguageCode("fr"),
            CurrencyCode("EUR"), FakeClock().now_utc()
        )
        with self.assertRaises(DowngradeExceedsCurrentUsage):
            merchant.change_plan(SubscriptionPlan.STARTER, 2)

    def test_change_plan_writes_plan_event_and_reports_downgrade_limit(self):
        merchant = Merchant.register(
            uuid4(), "Shop", CountryCode("FR"), LanguageCode("fr"),
            CurrencyCode("EUR"), FakeClock().now_utc()
        )
        merchants = FakeMerchants(merchant)
        use_case = ChangeSubscriptionPlanUseCase(
            merchants, FakeUsage(2), FakeUnitOfWork(), FakeOutbox(self.events), FakeClock()
        )
        with self.assertRaises(DowngradeExceedsCurrentUsage) as error:
            use_case.execute(merchant.id, "starter")
        self.assertEqual(error.exception.error_code, "DOWNGRADE_EXCEEDS_CURRENT_USAGE")

        result = use_case.execute(merchant.id, "pro")
        self.assertEqual(result["subscriptionPlan"], "pro")
        self.assertEqual(merchants.merchant.subscription_plan, SubscriptionPlan.PRO)
        self.assertEqual(len(self.events), 1)

    def test_refresh_rejects_disabled_user(self):
        self.use_case.execute("+14155550123", "long-password-123")
        user = self.users.by_phone["+14155550123"]
        self.users.by_id[user.id] = user.__class__(
            user.id, user.phone_number, user.email, user.password_hash,
            user.status.DISABLED, user.created_at,
        )
        refresh = RefreshAccessTokenUseCase(FakeTokens(user.id), self.users)
        with self.assertRaises(InvalidRefreshToken) as error:
            refresh.execute("refresh")
        self.assertEqual(error.exception.error_code, "INVALID_REFRESH_TOKEN")


class FakeUsers:
    def __init__(self):
        self.by_phone = {}
        self.by_id = {}

    def find_by_phone(self, phone_number):
        return self.by_phone.get(phone_number)

    def find_by_id(self, user_id):
        return self.by_id.get(user_id)

    def save(self, user):
        self.by_phone[user.phone_number.value] = user
        self.by_id[user.id] = user


class FakeHasher:
    def hash(self, password):
        return f"encoded:{password}"

    def verify(self, password, password_hash):
        return password_hash == f"encoded:{password}"


class FakeTokens:
    def __init__(self, user_id=None):
        self.user_id = user_id

    def issue_tokens(self, user_id):
        self.user_id = user_id
        return {"accessToken": "access", "refreshToken": "refresh"}

    def issue_access_token(self, user_id):
        return {"accessToken": "access", "expiresAt": datetime.now(timezone.utc)}

    def refresh_access_token(self, refresh_token):
        user_id = self.user_id or uuid4()
        return {**self.issue_access_token(user_id), "userId": user_id}


class FakeMerchants:
    def __init__(self, merchant):
        self.merchant = merchant

    def find_by_id(self, merchant_id):
        return self.merchant if self.merchant.id == merchant_id else None

    def save(self, merchant):
        self.merchant = merchant


class FakeUsage:
    def __init__(self, count):
        self.count = count

    def count_active_connections(self, merchant_id):
        return self.count


class FakeUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class FakeOutbox:
    def __init__(self, events):
        self.events = events

    def add(self, event):
        self.events.append(event)


class FakeClock:
    def now_utc(self):
        return datetime.now(timezone.utc)


if __name__ == "__main__":
    unittest.main()
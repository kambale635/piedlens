import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.payments.application.use_cases.start_payment_use_case import IdempotencyConflict, StartPaymentUseCase
from contexts.payments.domain.entities.payment_attempt import PaymentAttempt
from contexts.payments.domain.value_objects.payment_status import PaymentStatus
from contexts.payments.application.ports.payment_ports import ICheckoutInitiator


class FakePayables:
    def payable(self, merchant_id, payable_type, payable_id, options):
        return {"amount_minor": 1234, "currency": "USD", "country": "US", "plan_code": options["plan_code"]}


class FakeRoutes:
    def find_route(self, country, currency, method):
        return {"provider_code": "mock", "config": {}, "supports_escrow": False}


class FakeCheckout:
    def initiate(self, **kwargs):
        self.calls = getattr(self, "calls", []) + [kwargs]
        return {"outcome": "pending", "provider_reference": "mock-ref", "instructions": {"reference": str(kwargs["attempt_id"])}}


class FakeRegistry:
    def __init__(self):
        self.checkout = FakeCheckout()

    def require(self, code, capability):
        if code == "mock" and capability is ICheckoutInitiator:
            return self.checkout
        raise AssertionError("unexpected provider capability")


class FakePayments:
    def __init__(self):
        self.attempts = {}

    def create_attempt(self, attempt, key, request_hash):
        existing = self.attempts.get((attempt.merchant_id, key))
        if existing:
            prior, prior_hash = existing
            return prior, False, prior_hash != request_hash
        self.attempts[(attempt.merchant_id, key)] = (attempt, request_hash)
        return attempt, True, False

    def save_attempt(self, attempt):
        pass


class FakeUnitOfWork:
    def __enter__(self): return self
    def __exit__(self, *args): return False


class FakeOutbox:
    def add(self, event): pass


class Clock:
    def now_utc(self): return datetime(2026, 10, 26, tzinfo=timezone.utc)


class FeePolicy:
    def fee_minor(self, amount_minor, currency): return 25


class StartPaymentTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.payable_id = uuid4()
        self.payments = FakePayments()
        self.registry = FakeRegistry()
        self.use_case = StartPaymentUseCase(
            FakePayables(), FakeRoutes(), self.registry, self.payments,
            FakeUnitOfWork(), FakeOutbox(), Clock(), FeePolicy(),
        )

    def execute(self, plan="pro", key="key-1"):
        return self.use_case.execute(
            merchant_id=self.merchant_id, payable_type="subscription",
            payable_id=self.payable_id, method="manual", idempotency_key=key,
            payable_options={"plan_code": plan, "period_days": 30},
        )

    def test_server_price_is_used_and_same_idempotency_request_replays(self):
        result = self.execute()
        replay = self.execute()
        self.assertEqual(result["amountMinor"], 1234)
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["paymentAttemptId"], replay["paymentAttemptId"])
        self.assertEqual(len(self.registry.checkout.calls), 1)

    def test_same_key_different_content_conflicts(self):
        self.execute(plan="pro")
        with self.assertRaises(IdempotencyConflict):
            self.execute(plan="agency")


if __name__ == "__main__":
    unittest.main()

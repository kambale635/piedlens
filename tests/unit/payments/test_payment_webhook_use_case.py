import json
import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from contexts.payments.application.ports.payment_ports import IPaymentWebhookVerifier
from contexts.payments.application.use_cases.handle_payment_webhook_use_case import HandlePaymentWebhookUseCase
from contexts.payments.domain.entities.payment_attempt import PaymentAttempt
from contexts.payments.domain.value_objects.payment_proof_status import PaymentProofStatus
from contexts.payments.domain.value_objects.payment_status import PaymentStatus


class FakeVerifier:
    def verify(self, provider_code, raw_body, signature, timestamp):
        return signature == "valid"


class FakeRegistry:
    def require(self, provider_code, capability):
        if capability is IPaymentWebhookVerifier:
            return FakeVerifier()
        raise AssertionError(capability)


class FakeCache:
    def __init__(self):
        self.keys = set()

    def claim(self, provider, key, ttl):
        marker = (provider, key)
        if marker in self.keys:
            return False
        self.keys.add(marker)
        return True


class FakeRepository:
    def __init__(self, attempt):
        self.attempt = attempt
        self.events = {}

    def find_by_provider_event(self, provider, event_id):
        return self.events.get((provider, event_id))

    def find_for_update(self, attempt_id):
        return self.attempt if self.attempt.id == UUID(str(attempt_id)) else None

    def save_provider_event(self, provider, event_id, payload_hash, attempt_id):
        key = (provider, event_id)
        if key in self.events:
            return False
        self.events[key] = payload_hash
        return True

    def save_attempt(self, attempt):
        self.attempt = attempt


class FakeUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class FixedClock:
    def now_utc(self):
        return datetime(2026, 10, 26, tzinfo=timezone.utc)


class PaymentWebhookTests(unittest.TestCase):
    def setUp(self):
        now = datetime(2026, 10, 26, tzinfo=timezone.utc)
        self.attempt = PaymentAttempt(
            id=uuid4(), merchant_id=uuid4(), payable_type="subscription",
            payable_id=uuid4(), payable_reference="pro", provider_code="mock", amount_minor=1200,
            currency="USD", fee_minor=30, status=PaymentStatus.PENDING,
            provider_reference="mock-ref", proof_status=PaymentProofStatus.UNVERIFIED,
            expires_at=now + timedelta(minutes=15), created_at=now, updated_at=now,
        )
        self.repo = FakeRepository(self.attempt)
        self.cache = FakeCache()
        self.outbox = FakeOutbox()
        self.use_case = HandlePaymentWebhookUseCase(
            self.repo, FakeRegistry(), self.cache, FakeUnitOfWork(), self.outbox, FixedClock()
        )
        self.payload = {
            "event_id": "provider-event-1", "attempt_id": str(self.attempt.id),
            "amount_minor": 1200, "currency": "USD", "outcome": "succeeded",
            "provider_reference": "mock-ref",
        }

    def execute(self, payload=None):
        raw = json.dumps(payload or self.payload).encode()
        return self.use_case.execute("mock", raw, "valid", "2026-10-26T00:00:00Z")

    def test_signed_event_updates_attempt_and_emits_normalized_events_once(self):
        result = self.execute()
        replay = self.execute()
        self.assertEqual(result["outcome"], "succeeded")
        self.assertTrue(replay["duplicate"])
        self.assertEqual(self.repo.attempt.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(len(self.outbox.events), 2)

    def test_amount_mismatch_requires_review_without_success_event(self):
        payload = dict(self.payload, amount_minor=1201)
        result = self.execute(payload)
        self.assertEqual(result["outcome"], "needs_review")
        self.assertNotEqual(self.repo.attempt.status, PaymentStatus.SUCCEEDED)

    def test_invalid_signature_is_rejected_before_processing(self):
        raw = json.dumps(self.payload).encode()
        with self.assertRaises(Exception):
            self.use_case.execute("mock", raw, "invalid", "2026-10-26T00:00:00Z")
        self.assertEqual(self.repo.events, {})


if __name__ == "__main__":
    unittest.main()

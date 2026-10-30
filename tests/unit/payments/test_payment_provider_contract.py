import unittest
import hashlib
import hmac
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from contexts.payments.application.ports.payment_ports import ICheckoutInitiator
from contexts.payments.application.services.payment_provider_registry import PaymentProviderRegistry
from contexts.payments.infrastructure.adapters.mock_payment_provider import MockPaymentProvider


class FakePaymentProvider:
    def initiate(self, **kwargs):
        return {"outcome": "pending", "provider_reference": "fake-ref"}


class PaymentProviderContractTests(unittest.TestCase):
    def test_fake_provider_can_be_registered_at_runtime(self):
        adapter = FakePaymentProvider()
        registry = PaymentProviderRegistry({"fake_payment_provider": {ICheckoutInitiator: adapter}})
        result = registry.require("fake_payment_provider", ICheckoutInitiator).initiate(
            attempt_id=uuid4(), amount_minor=100, currency="USD", idempotency_key="key"
        )
        self.assertEqual(result["outcome"], "pending")
        self.assertEqual(result["provider_reference"], "fake-ref")

    def test_mock_webhook_requires_secret_and_fresh_timestamp(self):
        provider = MockPaymentProvider()
        body = b'{"event":"payment"}'
        now = str(int(datetime.now(timezone.utc).timestamp()))
        with patch(
            "contexts.payments.infrastructure.adapters.mock_payment_provider.settings.PAYMENT_WEBHOOK_SECRETS",
            {"mock": "local-test-secret"},
        ):
            signature = hmac.new(
                b"local-test-secret", now.encode() + b"." + body, hashlib.sha256
            ).hexdigest()
            self.assertTrue(provider.verify("mock", body, signature, now))
            old_timestamp = str(int(now) - 10000)
            old_signature = hmac.new(
                b"local-test-secret", old_timestamp.encode() + b"." + body, hashlib.sha256
            ).hexdigest()
            self.assertFalse(provider.verify("mock", body, old_signature, old_timestamp))
        with patch(
            "contexts.payments.infrastructure.adapters.mock_payment_provider.settings.PAYMENT_WEBHOOK_SECRETS",
            {"mock": ""},
        ):
            self.assertFalse(provider.verify("mock", body, "local", now))


if __name__ == "__main__":
    unittest.main()

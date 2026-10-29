import unittest
from uuid import uuid4

from contexts.payments.application.ports.payment_ports import ICheckoutInitiator
from contexts.payments.application.services.payment_provider_registry import PaymentProviderRegistry


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


if __name__ == "__main__":
    unittest.main()

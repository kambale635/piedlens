import unittest
from unittest.mock import patch
from uuid import uuid4

from piedlens_platform.di.container import ApplicationContainer
from piedlens_platform.event_bus.handlers import handle_payment_succeeded


class ConsumePaymentSucceededTests(unittest.TestCase):
    def test_payment_event_dispatch_uses_identity_consumer(self):
        event_id, merchant_id = uuid4(), uuid4()
        envelope = {
            "eventId": str(event_id),
            "eventType": "PaymentSucceeded",
            "payload": {
                "payable_type": "subscription",
                "payable_id": str(merchant_id),
                "merchant_id": str(merchant_id),
                "payable_reference": "pro",
            },
        }
        with patch.object(ApplicationContainer, "consume_payment_succeeded") as factory:
            consumer = unittest.mock.Mock()
            factory.return_value = consumer
            handle_payment_succeeded(envelope)
        factory.assert_called_once_with()
        consumer.execute.assert_called_once_with(
            event_id=event_id, merchant_id=merchant_id, plan_code="pro"
        )

    def test_non_subscription_payment_does_not_change_plan(self):
        envelope = {"eventType": "PaymentSucceeded", "payload": {"payable_type": "order"}}
        with patch.object(ApplicationContainer, "consume_payment_succeeded") as factory:
            handle_payment_succeeded(envelope)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()

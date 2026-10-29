import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase, override_settings

from contexts.billing.infrastructure.persistence.models import (
    PlanDefinitionRecord,
    PlanPriceRecord,
)
from contexts.identity.infrastructure.persistence.models import MerchantRecord
from contexts.payments.infrastructure.models import (
    OutboxEventRecord,
    PaymentAttemptRecord,
    PaymentRouteRecord,
    PaymentProviderEventRecord,
)


class AllowPaymentPermissions:
    def can(self, **kwargs):
        return True


class PaymentApiTests(TestCase):
    def setUp(self):
        call_command("seed_billing_plans", verbosity=0)
        self.merchant_id = uuid4()
        self.user_id = uuid4()
        now = datetime.now(timezone.utc)
        self.user = __import__(
            "contexts.identity.infrastructure.persistence.models",
            fromlist=["UserRecord"],
        ).UserRecord.objects.create(
            id=self.user_id, phone_number=f"+1415{uuid4().int % 10**7:07d}",
            email=None, password_hash="test", status="active", created_at=now,
        )
        MerchantRecord.objects.create(
            id=self.merchant_id, name="Payment test", country="US",
            preferred_language="en", currency="USD", subscription_plan="discovery",
            created_at=now,
        )
        pro = PlanDefinitionRecord.objects.get(code="pro")
        PlanPriceRecord.objects.update_or_create(
            plan=pro, country="US", currency="USD", period_days=30,
            defaults={"amount_minor": 500, "is_active": True},
        )
        PaymentRouteRecord.objects.create(
            country="US", currency="USD", method="manual", provider_code="mock",
            priority=1, active=True, supports_escrow=False,
        )
        self.headers = {
            "HTTP_AUTHORIZATION": f"Bearer {self._issue_access_token()}",
            "HTTP_X_MERCHANT_ID": str(self.merchant_id),
        }

    @override_settings(
        PIEDLENS_PERMISSION_CHECKER=AllowPaymentPermissions(),
        PAYMENT_WEBHOOK_SECRETS={"mock": "payments-test-secret"},
    )
    def test_subscription_checkout_uses_server_price_and_signed_webhook_is_idempotent(self):
        with override_settings(PIEDLENS_PERMISSION_CHECKER=AllowPaymentPermissions()):
            response = self.client.post(
                "/api/v1/payments/checkout",
                data=json.dumps({"planCode": "pro", "periodDays": 30, "method": "manual"}),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="subscription-test-1",
                **self.headers,
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["amountMinor"], 500)
        self.assertEqual(response.json()["currency"], "USD")
        attempt_id = response.json()["paymentAttemptId"]
        self.assertEqual(PaymentAttemptRecord.objects.get(id=attempt_id).payable_reference, "pro")

        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        body = json.dumps({
            "event_id": "mock-event-1", "attempt_id": str(attempt_id),
            "amount_minor": 500, "currency": "USD", "outcome": "succeeded",
            "provider_reference": f"mock:{attempt_id}",
        }, separators=(",", ":")).encode()
        signature = hmac.new(
            b"payments-test-secret", timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        webhook = self.client.post(
            "/api/v1/webhooks/payments/mock", data=body, content_type="application/json",
            HTTP_X_PAYMENT_SIGNATURE=f"sha256={signature}",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )
        self.assertEqual(webhook.status_code, 200, webhook.content)
        self.assertEqual(webhook.json()["outcome"], "succeeded")
        replay = self.client.post(
            "/api/v1/webhooks/payments/mock", data=body, content_type="application/json",
            HTTP_X_PAYMENT_SIGNATURE=f"sha256={signature}",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )
        self.assertTrue(replay.json()["duplicate"])
        self.assertEqual(PaymentProviderEventRecord.objects.count(), 1)
        self.assertTrue(OutboxEventRecord.objects.filter(event_type="PaymentSucceeded").exists())

    def _issue_access_token(self):
        from contexts.identity.infrastructure.adapters.django_security_services import DjangoTokenService

        return DjangoTokenService().issue_tokens(self.user_id)["accessToken"]

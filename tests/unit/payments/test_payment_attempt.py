import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.payments.domain.entities.payment_attempt import PaymentAttempt
from contexts.payments.domain.exceptions.payment_exceptions import InvalidPaymentTransition
from contexts.payments.domain.value_objects.payment_proof_status import PaymentProofStatus
from contexts.payments.domain.value_objects.payment_status import PaymentStatus


class PaymentAttemptTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 26, tzinfo=timezone.utc)
        self.attempt = PaymentAttempt(
            id=uuid4(), merchant_id=uuid4(), payable_type="subscription",
            payable_id=uuid4(), payable_reference="pro", provider_code="mock", amount_minor=1200,
            currency="USD", fee_minor=30, status=PaymentStatus.CREATED,
            provider_reference=None, proof_status=PaymentProofStatus.UNVERIFIED,
            expires_at=self.now + timedelta(minutes=15), created_at=self.now,
            updated_at=self.now,
        )

    def test_transition_table_created_pending_terminal(self):
        self.attempt.mark_pending("provider-1", self.now)
        self.assertEqual(self.attempt.status, PaymentStatus.PENDING)
        event = self.attempt.apply_provider_result(
            event_amount_minor=1200, event_currency="USD", outcome="succeeded",
            provider_reference="provider-1", occurred_at=self.now,
        )
        self.assertEqual(self.attempt.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(event.amount_minor, 1200)
        self.assertEqual(event.currency, "USD")

    def test_amount_currency_mismatch_requires_review_without_success_event(self):
        self.attempt.mark_pending("provider-1", self.now)
        result = self.attempt.apply_provider_result(
            event_amount_minor=1201, event_currency="USD", outcome="succeeded",
            provider_reference="provider-1", occurred_at=self.now,
        )
        self.assertEqual(result, "needs_review")
        self.assertEqual(self.attempt.status, PaymentStatus.NEEDS_REVIEW)

    def test_late_success_after_expiry_requires_review(self):
        self.attempt.mark_pending("provider-1", self.now)
        self.attempt.expire(self.attempt.expires_at)
        result = self.attempt.apply_provider_result(
            event_amount_minor=1200, event_currency="USD", outcome="succeeded",
            provider_reference="provider-1", occurred_at=self.attempt.expires_at + timedelta(seconds=1),
        )
        self.assertIsNone(result)
        self.assertEqual(self.attempt.status, PaymentStatus.NEEDS_REVIEW)

    def test_unverified_proof_does_not_succeed_but_explicit_seller_confirmation_can(self):
        self.attempt.mark_pending(None, self.now)
        self.attempt.apply_unverified_proof(self.now)
        self.assertEqual(self.attempt.status, PaymentStatus.PENDING)
        event = self.attempt.confirm_seller_proof(self.now)
        self.assertEqual(self.attempt.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(event.amount_minor, 1200)
        self.assertEqual(self.attempt.proof_status, PaymentProofStatus.SELLER_CONFIRMED)

    def test_invalid_transition_is_rejected(self):
        with self.assertRaises(InvalidPaymentTransition):
            self.attempt.apply_provider_result(
                event_amount_minor=1200, event_currency="USD", outcome="succeeded",
                provider_reference="x", occurred_at=self.now,
            )


if __name__ == "__main__":
    unittest.main()

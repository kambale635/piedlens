import hashlib
import json
from uuid import uuid4

from shared_kernel.application_exceptions import ValidationException

from ...domain.events.payment_events import ExternalPaymentReceived, PaymentRefundRequested
from ...domain.value_objects.payment_status import PaymentStatus
from ..ports.payment_ports import IPaymentWebhookVerifier, IPaymentRepository


class HandlePaymentWebhookUseCase:
    """Verify, deduplicate, reconcile, and record one provider result (INV-PAY-01/02/06/T2/T7)."""

    def __init__(self, payments: IPaymentRepository, registry, replay_cache, unit_of_work, outbox, clock):
        self._payments = payments
        self._registry = registry
        self._replay_cache = replay_cache
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(self, provider_code, raw_body, signature, timestamp):
        verifier: IPaymentWebhookVerifier = self._registry.require(provider_code, IPaymentWebhookVerifier)
        if not verifier.verify(provider_code, raw_body, signature, timestamp):
            raise ValidationException("Invalid payment provider signature.")
        payload_hash = hashlib.sha256(raw_body).hexdigest()
        try:
            payload = json.loads(raw_body)
        except (ValueError, TypeError) as error:
            raise ValidationException("Payment webhook payload is malformed.") from error
        required = {"event_id", "attempt_id", "amount_minor", "currency", "outcome", "provider_reference"}
        if not required.issubset(payload):
            raise ValidationException("Payment webhook lacks required fields.")
        now = self._clock.now_utc()
        with self._unit_of_work:
            duplicate = self._payments.find_by_provider_event(provider_code, payload["event_id"])
            if duplicate is not None:
                return {"accepted": True, "duplicate": True, "outcome": "ignored"}
            attempt = self._payments.find_for_update(payload["attempt_id"])
            if attempt is None or attempt.provider_code != provider_code:
                raise ValidationException("Payment attempt/provider mismatch.")
            if not self._payments.save_provider_event(provider_code, payload["event_id"], payload_hash, attempt.id):
                return {"accepted": True, "duplicate": True, "outcome": "ignored"}
            prior_status = attempt.status
            result = attempt.apply_provider_result(
                event_amount_minor=payload["amount_minor"],
                event_currency=payload["currency"],
                outcome=payload["outcome"],
                provider_reference=payload["provider_reference"],
                occurred_at=now,
            )
            self._payments.save_attempt(attempt)
            self._outbox.add(ExternalPaymentReceived.create(
                attempt.id, provider_code, payload["event_id"], attempt.merchant_id,
                payload["amount_minor"], payload["currency"], payload["outcome"],
                payload["provider_reference"], now,
            ))
            if prior_status == PaymentStatus.SUCCEEDED and payload["outcome"] == "succeeded":
                self._payments.save_attempt(attempt)
                self._outbox.add(PaymentRefundRequested(
                    uuid4(), attempt.id, attempt.payable_id,
                    payload["provider_reference"], now,
                ))
            elif result is not None and result != "needs_review":
                self._outbox.add(result)
        self._replay_cache.claim(provider_code, payload["event_id"], 600)
        return {"accepted": True, "duplicate": False, "outcome": attempt.status.value}

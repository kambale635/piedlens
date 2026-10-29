import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from shared_kernel.application_exceptions import ResourceNotFoundException, ValidationException
from shared_kernel.domain_exceptions import DomainException

from ...domain.entities.payment_attempt import PaymentAttempt
from ...domain.value_objects.payment_proof_status import PaymentProofStatus
from ...domain.value_objects.payment_status import PaymentStatus
from ..ports.payment_ports import ICheckoutInitiator, IPaymentRepository


class IdempotencyConflict(DomainException):
    """An idempotency key was reused with different request content (INV-PAY-02/T7)."""


class StartPaymentUseCase:
    """Start a server-priced checkout for one payable (INV-PAY-01/02/05/07/T5/T7/T8)."""

    def __init__(self, payable_reader, route_reader, provider_registry, payments: IPaymentRepository,
                 unit_of_work, outbox, clock, fee_policy, checkout_ttl_seconds=900):
        self._payables = payable_reader
        self._routes = route_reader
        self._providers = provider_registry
        self._payments = payments
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock
        self._fee_policy = fee_policy
        self._ttl = checkout_ttl_seconds

    def execute(self, merchant_id, payable_type, payable_id, method, idempotency_key,
                payable_options=None):
        if not idempotency_key or len(idempotency_key) > 160:
            raise ValidationException("Idempotency-Key is required and must be at most 160 characters.")
        payable = self._payables.payable(
            merchant_id, payable_type, payable_id, payable_options or {}
        )
        if payable is None:
            raise ResourceNotFoundException("Payable was not found.")
        amount_minor = payable.get("amount_minor")
        currency = payable.get("currency")
        if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor < 0:
            raise ValidationException("Payable amount must be server-calculated non-negative minor units.")
        if not isinstance(currency, str) or len(currency) != 3:
            raise ValidationException("Payable currency is required.")
        route = self._routes.find_route(payable["country"], currency, method)
        if route is None:
            raise ValidationException("No payment route is configured for this country, currency, and method.")
        body = {
            "payable_type": payable_type,
            "payable_id": str(payable_id),
            "method": method,
            "payable_options": payable_options or {},
        }
        request_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        now = self._clock.now_utc()
        attempt = PaymentAttempt(
            id=uuid4(), merchant_id=merchant_id, payable_type=payable_type, payable_id=payable_id,
            payable_reference=payable.get("plan_code", ""),
            provider_code=route["provider_code"], amount_minor=amount_minor, currency=currency.upper(),
            fee_minor=self._fee_policy.fee_minor(amount_minor, currency), status=PaymentStatus.CREATED,
            provider_reference=None, proof_status=PaymentProofStatus.UNVERIFIED,
            expires_at=now + timedelta(seconds=self._ttl), created_at=now, updated_at=now,
        )
        with self._unit_of_work:
            attempt, created, conflict = self._payments.create_attempt(attempt, idempotency_key, request_hash)
            if conflict:
                raise IdempotencyConflict("Idempotency-Key was reused with different content. INV-PAY-02/T7")
            if not created:
                return {"paymentAttemptId": attempt.id, "status": attempt.status.value,
                        "amountMinor": attempt.amount_minor, "currency": attempt.currency}
            checkout: ICheckoutInitiator = self._providers.require(route["provider_code"], ICheckoutInitiator)
            result = checkout.initiate(
                attempt_id=attempt.id, amount_minor=attempt.amount_minor,
                currency=attempt.currency, idempotency_key=idempotency_key,
            )
            if result["outcome"] == "pending":
                attempt.mark_pending(result.get("provider_reference"), now)
            elif result["outcome"] in {"succeeded", "failed"}:
                attempt.mark_pending(result.get("provider_reference"), now)
                event = attempt.apply_provider_result(
                    event_amount_minor=amount_minor, event_currency=currency,
                    outcome=result["outcome"], provider_reference=result.get("provider_reference", ""),
                    occurred_at=now,
                )
                if event:
                    self._outbox.add(event)
            self._payments.save_attempt(attempt)
        return {"paymentAttemptId": attempt.id, "status": attempt.status.value,
                "amountMinor": attempt.amount_minor, "currency": attempt.currency,
            "instructions": result.get("instructions"),
            "providerReference": attempt.provider_reference,
            "duplicate": False}

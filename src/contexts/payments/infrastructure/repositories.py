from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from uuid import uuid4

from django.db import transaction

from ..domain.entities.payment_attempt import PaymentAttempt
from ..domain.events.payment_events import PaymentSucceeded
from ..domain.value_objects.payment_proof_status import PaymentProofStatus
from ..domain.value_objects.payment_status import PaymentStatus
from .models import (
    OutboxEventRecord,
    PaymentAttemptRecord,
    PaymentEventRecord,
    PaymentProviderEventRecord,
    PaymentRouteRecord,
    ProcessedEventRecord,
)


class DjangoPaymentRepository:
    """Persist PaymentAttempt and provider-event idempotency in Payments (INV-PAY-01/02/06)."""

    def create_attempt(self, attempt, idempotency_key, request_hash):
        existing = PaymentAttemptRecord.objects.filter(merchant_id=attempt.merchant_id, idempotency_key=idempotency_key).first()
        if existing:
            if existing.request_hash != request_hash:
                return self._to_domain(existing), False, True
            return self._to_domain(existing), False, False
        PaymentAttemptRecord.objects.create(
            id=attempt.id, merchant_id=attempt.merchant_id,
            payable_type=attempt.payable_type, payable_id=attempt.payable_id,
            payable_reference=attempt.payable_reference,
            provider_code=attempt.provider_code, amount_minor=attempt.amount_minor,
            currency=attempt.currency, fee_minor=attempt.fee_minor,
            status=attempt.status.value, proof_status=attempt.proof_status.value,
            provider_reference=attempt.provider_reference, idempotency_key=idempotency_key,
            request_hash=request_hash, expires_at=attempt.expires_at,
            created_at=attempt.created_at, updated_at=attempt.updated_at,
        )
        return attempt, True, False

    def find_for_update(self, attempt_id):
        record = PaymentAttemptRecord.objects.select_for_update().filter(id=attempt_id).first()
        return self._to_domain(record) if record else None

    def find_by_provider_event(self, provider_code, event_id):
        return PaymentProviderEventRecord.objects.filter(provider_code=provider_code, provider_event_id=event_id).first()

    def save_provider_event(self, provider_code, event_id, payload_hash, attempt_id):
        _, created = PaymentProviderEventRecord.objects.get_or_create(
            provider_code=provider_code, provider_event_id=event_id,
            defaults={"payload_hash": payload_hash, "payment_attempt_id": attempt_id},
        )
        return created

    def save_attempt(self, attempt):
        PaymentAttemptRecord.objects.filter(id=attempt.id).update(
            status=attempt.status.value, proof_status=attempt.proof_status.value,
            provider_reference=attempt.provider_reference, updated_at=attempt.updated_at,
        )

    @staticmethod
    def _to_domain(record):
        return PaymentAttempt(
            id=record.id, merchant_id=record.merchant_id, payable_type=record.payable_type,
            payable_id=record.payable_id, payable_reference=record.payable_reference,
            provider_code=record.provider_code,
            amount_minor=record.amount_minor, currency=record.currency, fee_minor=record.fee_minor,
            status=PaymentStatus(record.status), provider_reference=record.provider_reference,
            proof_status=PaymentProofStatus(record.proof_status), expires_at=record.expires_at,
            created_at=record.created_at, updated_at=record.updated_at,
        )


class DjangoPaymentOutbox:
    """Append payment domain events to the same Payments transaction (INV-TR-02)."""

    def add(self, event):
        values = {field.name: getattr(event, field.name) for field in fields(event)}
        event_id = values.pop("event_id", uuid4())
        occurred_at = values.pop("occurred_at", datetime.now(timezone.utc))
        payload = self._json(values)
        OutboxEventRecord.objects.create(event_id=event_id, event_type=type(event).__name__, occurred_at=occurred_at, payload=payload)
        if isinstance(event, PaymentSucceeded):
            PaymentEventRecord.objects.create(
                event_id=event_id, payment_attempt_id=event.payment_attempt_id,
                merchant_id=event.merchant_id, event_type="succeeded",
                amount_minor=event.amount_minor, currency=event.currency,
                occurred_at=event.occurred_at, metadata={"fee_minor": event.fee_minor},
            )

    @classmethod
    def _json(cls, value):
        from datetime import datetime
        from uuid import UUID
        if is_dataclass(value):
            return cls._json({field.name: getattr(value, field.name) for field in fields(value)})
        if isinstance(value, (UUID, datetime)):
            return value.isoformat() if isinstance(value, datetime) else str(value)
        if isinstance(value, dict):
            return {key: cls._json(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [cls._json(item) for item in value]
        return value


class DjangoPaymentRouteReader:
    def find_route(self, country, currency, method):
        record = PaymentRouteRecord.objects.filter(country=country, currency=currency, method=method, active=True).order_by("priority", "provider_code").first()
        if record is None:
            return None
        return {"provider_code": record.provider_code, "config": record.config, "supports_escrow": record.supports_escrow}


class DjangoPaymentPriceReader:
    """Read PaymentRoute data only; subscription prices use a composition adapter (INV-PAY-01/05/T5)."""

    def upsert(self, route):
        PaymentRouteRecord.objects.update_or_create(
            country=route["country"], currency=route["currency"],
            method=route["method"], provider_code=route["provider_code"],
            defaults={
                "priority": route["priority"], "active": route["active"],
                "supports_escrow": route["supports_escrow"], "config": route["config"],
            },
        )


class DjangoProcessedPaymentEventRepository:
    def has_processed(self, event_id, consumer_name):
        return ProcessedEventRecord.objects.filter(event_id=event_id, consumer_name=consumer_name).exists()

    def mark_processed(self, event_id, consumer_name):
        _, created = ProcessedEventRecord.objects.get_or_create(event_id=event_id, consumer_name=consumer_name)
        return created

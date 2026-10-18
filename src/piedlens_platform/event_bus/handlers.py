"""Composition-layer handlers translating Redis envelopes into application calls."""

from datetime import datetime
from decimal import Decimal
from importlib import import_module
from uuid import UUID

from django.conf import settings

from contexts.order_detection.application.ports.detection_configuration import (
    DetectionConfiguration,
)
from contexts.order_detection.application.dto.evaluation_result import EvaluationResult
from piedlens_platform.di.container import ApplicationContainer
from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money


def _uuid(value):
    return UUID(str(value))


def _datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def handle_message_received(envelope):
    """Dispatch one normalized connector message to CRM and Rules Engine."""
    payload = envelope["payload"]
    context = envelope["producedBy"]
    if context != "platform-connectors":
        return
    if envelope["eventType"] != "MessageReceived":
        return
    event_id = _uuid(envelope["eventId"])
    merchant_id = _uuid(payload["merchant_id"])
    connection_id = _uuid(payload["platform_connection_id"])
    if settings.CONSUMER_CONTEXT == "crm":
        ApplicationContainer.update_contact_from_message().execute(
            event_id=event_id,
            merchant_id=merchant_id,
            platform_connection_id=connection_id,
            external_identifier=payload["external_sender_id"],
            display_name=payload.get("display_name", ""),
            timestamp=_datetime(payload["received_at"]),
        )
        return
    if settings.CONSUMER_CONTEXT == "backup":
        ApplicationContainer.create_backup_snapshot().execute(connection_id)
        return
    if settings.CONSUMER_CONTEXT == "rules-engine":
        from contexts.platform_connectors.infrastructure.adapters.django_message_content_cipher import (
            DjangoMessageContentCipher,
        )

        ApplicationContainer.evaluate_message().execute(
            merchant_id=merchant_id,
            message_id=_uuid(payload["message_id"]),
            text_content=DjangoMessageContentCipher().decrypt(payload.get("text_content", "")),
            has_media=bool(payload.get("has_media", False)),
            event_id=event_id,
            platform_connection_id=connection_id,
            external_sender_id=payload["external_sender_id"],
            display_name=payload.get("display_name", ""),
            message_event_id=event_id,
            source_message_timestamp=_datetime(payload["received_at"]),
        )


def handle_message_evaluated(envelope):
    """Resolve the CRM identity through its application use case before detection."""
    payload = envelope["payload"]
    if envelope["eventType"] != "MessageEvaluated":
        return
    connection_id = payload.get("platform_connection_id")
    external_sender_id = payload.get("external_sender_id")
    source_timestamp = payload.get("source_message_timestamp")
    if not connection_id or not external_sender_id or not source_timestamp:
        raise ValueError("MessageEvaluated lacks the CRM identity fields required for detection")
    event_id = _uuid(envelope["eventId"])
    message_event_id = _uuid(payload.get("message_event_id") or envelope["eventId"])
    merchant_id = _uuid(payload["merchant_id"])
    contact = ApplicationContainer.update_contact_from_message().execute(
        event_id=message_event_id,
        merchant_id=merchant_id,
        platform_connection_id=_uuid(connection_id),
        external_identifier=external_sender_id,
        display_name=payload.get("display_name", ""),
        timestamp=_datetime(source_timestamp),
    )
    extracted = payload.get("extracted_data") or {}
    raw_amount = extracted.get("amount")
    amount = None
    if isinstance(raw_amount, dict):
        amount = Money(Decimal(str(raw_amount["amount"])), raw_amount["currency"])
    evaluation = EvaluationResult(
        confidence_score=ConfidenceScore(int(payload["confidence_score"])),
        intent=extracted.get("intent"),
        amount=amount,
        matched_rule_ids=tuple(_uuid(item) for item in payload.get("matched_rule_ids", [])),
    )
    configuration = DetectionConfiguration(
        confidence_threshold=settings.ORDER_DETECTION_CONFIDENCE_THRESHOLD,
        correlation_window_days=settings.ORDER_DETECTION_CORRELATION_WINDOW_DAYS,
    )
    ApplicationContainer.detect_order(_StaticDetectionConfiguration(configuration)).execute(
        merchant_id=merchant_id,
        event_id=event_id,
        contact_id=contact.contact_id,
        evaluation_result=evaluation,
        source_message_id=_uuid(payload["message_id"]),
        source_message_timestamp=_datetime(source_timestamp),
    )


def handle_order_status_changed(envelope):
    """Apply OrderStatusChanged to CRM purchase history without cross-table reads."""
    if envelope["eventType"] != "OrderStatusChanged":
        return
    payload = envelope["payload"]
    amount = payload["detected_amount"]
    ApplicationContainer.update_contact_from_order().execute(
        event_id=_uuid(envelope["eventId"]),
        contact_id=_uuid(payload["contact_id"]),
        order_id=_uuid(payload["order_id"]),
        status=payload["status"],
        order_amount=Money(Decimal(str(amount["amount"])), amount["currency"]),
        updated_at=_datetime(payload["updated_at"]),
    )


def handle_merchant_data_deleted(envelope):
    """Dispatch Backup deletion events to the configured context-owned purge handler (INV-BK-06)."""
    if envelope.get("producedBy") != "backup" or envelope.get("eventType") != "MerchantDataDeleted":
        return
    context = settings.CONSUMER_CONTEXT
    handlers = {
        "identity": "contexts.identity.infrastructure.messaging.merchant_data_deletion_handler",
        "access-control": "contexts.access_control.infrastructure.messaging.merchant_data_deletion_handler",
        "platform-connectors": "contexts.platform_connectors.infrastructure.messaging.merchant_data_deletion_handler",
        "rules-engine": "contexts.rules_engine.infrastructure.messaging.merchant_data_deletion_handler",
        "order-detection": "contexts.order_detection.infrastructure.messaging.merchant_data_deletion_handler",
        "crm": "contexts.crm.infrastructure.messaging.merchant_data_deletion_handler",
    }
    module_path = handlers.get(context)
    if module_path is None:
        raise ValueError("MerchantDataDeleted consumer context is not configured.")
    import_module(module_path).handle_merchant_data_deleted(envelope)


class _StaticDetectionConfiguration:
    def __init__(self, configuration):
        self._configuration = configuration

    def for_merchant(self, merchant_id):
        return self._configuration
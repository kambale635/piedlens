"""Module: contexts.order_detection.infrastructure.adapters.django_order_status_intent_configuration
Context: Order Detection.
Role: resolve status intent labels from Rules Engine-owned persisted configuration.
"""

from uuid import UUID

from django.conf import settings

from contexts.rules_engine.infrastructure.persistence.models import RuleSetRecord

from ...application.ports.detection_configuration import (
    DetectionConfiguration,
    IDetectionConfiguration,
)


class DjangoOrderStatusIntentConfiguration(IDetectionConfiguration):
    """Read configured intent labels while reusing the detection correlation window (INV-RE-04/OD-09)."""

    def for_merchant(self, merchant_id: UUID) -> DetectionConfiguration:
        """Return the configured correlation window and detection threshold."""
        return DetectionConfiguration(
            confidence_threshold=settings.ORDER_DETECTION_CONFIDENCE_THRESHOLD,
            correlation_window_days=settings.ORDER_DETECTION_CORRELATION_WINDOW_DAYS,
        )

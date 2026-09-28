"""Module: contexts/crm/infrastructure/django_relationship_anomaly_configuration.py
Context: CRM.
Role: resolve anomaly policy from Django deployment settings (INV-CRM-05).
"""

from uuid import UUID

from django.conf import settings

from ..application.ports import IRelationshipAnomalyConfiguration
from ..domain.relationship_anomaly_policy import RelationshipAnomalyPolicy


class DjangoRelationshipAnomalyConfiguration(IRelationshipAnomalyConfiguration):
    """Read deployment defaults and optional merchant overrides from settings."""

    def for_merchant(self, merchant_id: UUID) -> RelationshipAnomalyPolicy:
        """Build a validated policy for one merchant without domain-level defaults."""
        merchant_policies = getattr(
            settings, "CRM_RELATIONSHIP_ANOMALY_BY_MERCHANT", {}
        )
        override = merchant_policies.get(str(merchant_id), {})
        return RelationshipAnomalyPolicy(
            min_purchases=override.get(
                "min_purchases", settings.CRM_ANOMALY_MIN_PURCHASES
            ),
            anomaly_multiplier=override.get(
                "anomaly_multiplier", settings.CRM_ANOMALY_MULTIPLIER
            ),
            min_inactivity_days=override.get(
                "min_inactivity_days", settings.CRM_ANOMALY_MIN_INACTIVITY_DAYS
            ),
        )
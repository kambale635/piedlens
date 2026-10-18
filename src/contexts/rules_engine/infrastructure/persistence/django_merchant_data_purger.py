"""Module: contexts/rules_engine/infrastructure/persistence/django_merchant_data_purger.py
Context: Rules Engine
Role: delete only merchant-scoped RuleSet aggregates with resumable progress.
"""

from django.db import transaction

from .models import MerchantDeletionProgressRecord, RuleSetRecord


class DjangoRulesEngineMerchantPurger:
    """Delete merchant RuleSets individually while preserving country and global rules (INV-RE-05)."""

    def purge_merchant_rule_sets(self, event_id, merchant_id) -> None:
        """Delete each matching RuleSet with its progress marker in one transaction (INV-RE-05, INV-TR-01)."""
        scope = f"merchant:{merchant_id}"
        rule_set_ids = list(
            RuleSetRecord.objects.filter(scope=scope)
            .order_by("id")
            .values_list("id", flat=True)
        )
        for rule_set_id in rule_set_ids:
            with transaction.atomic():
                if MerchantDeletionProgressRecord.objects.filter(
                    event_id=event_id,
                    rule_set_id=rule_set_id,
                ).exists():
                    continue
                RuleSetRecord.objects.filter(id=rule_set_id, scope=scope).delete()
                MerchantDeletionProgressRecord.objects.create(
                    event_id=event_id,
                    merchant_id=merchant_id,
                    rule_set_id=rule_set_id,
                )
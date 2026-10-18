from uuid import uuid4

from django.test import TestCase

from contexts.rules_engine.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase,
)
from contexts.rules_engine.infrastructure.messaging.merchant_data_deletion_handler import (
    handle_merchant_data_deleted,
)
from contexts.rules_engine.infrastructure.persistence.models import (
    MerchantDeletionProgressRecord,
    OutboxEventRecord,
    ProcessedEventRecord,
    RuleSetRecord,
)


class RulesEngineMerchantDataDeletionTests(TestCase):
    def test_purge_removes_only_the_target_merchant_rules(self):
        merchant_id = uuid4()
        other_merchant_id = uuid4()
        event_id = uuid4()
        target = RuleSetRecord.objects.create(
            scope=f"merchant:{merchant_id}", rules=[{"keyword": "private"}]
        )
        other = RuleSetRecord.objects.create(
            scope=f"merchant:{other_merchant_id}", rules=[{"keyword": "other"}]
        )
        country = RuleSetRecord.objects.create(
            scope="country:FR", rules=[{"keyword": "country"}]
        )
        global_rules = RuleSetRecord.objects.create(
            scope="global", rules=[{"keyword": "global"}]
        )
        envelope = {
            "eventId": str(event_id),
            "eventType": "MerchantDataDeleted",
            "producedBy": "backup",
            "payload": {"merchant_id": str(merchant_id)},
        }

        handle_merchant_data_deleted(envelope)
        handle_merchant_data_deleted(envelope)

        self.assertFalse(RuleSetRecord.objects.filter(id=target.id).exists())
        self.assertTrue(RuleSetRecord.objects.filter(id=other.id).exists())
        self.assertTrue(RuleSetRecord.objects.filter(id=country.id).exists())
        self.assertTrue(RuleSetRecord.objects.filter(id=global_rules.id).exists())
        self.assertEqual(
            ProcessedEventRecord.objects.filter(
                event_id=event_id,
                consumer_name=PurgeMerchantDataUseCase.CONSUMER_NAME,
            ).count(),
            1,
        )
        self.assertEqual(
            OutboxEventRecord.objects.filter(
                event_type="MerchantDataPurged",
                payload__context="rules-engine",
                payload__merchant_id=str(merchant_id),
            ).count(),
            1,
        )
        self.assertEqual(MerchantDeletionProgressRecord.objects.filter(event_id=event_id).count(), 1)
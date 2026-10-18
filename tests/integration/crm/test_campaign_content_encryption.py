import base64
from datetime import datetime, timezone
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase, override_settings

from contexts.crm.domain.entities.bulk_message_campaign import BulkMessageCampaign
from contexts.crm.infrastructure.persistence.django_bulk_message_campaign_repository import (
    DjangoBulkMessageCampaignRepository,
)
from contexts.crm.infrastructure.persistence.models import (
    BulkMessageCampaignRecord,
    BulkMessageRecipientRecord,
)


class CampaignContentEncryptionTests(TestCase):
    def test_campaign_template_is_encrypted_at_rest_and_decrypted_for_delivery(self):
        content = "private campaign message"
        campaign = BulkMessageCampaign.create(
            merchant_id=uuid4(),
            segment_id=uuid4(),
            channel="whatsapp",
            template=content,
            recipient_contact_ids=(uuid4(),),
            created_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        )
        repository = DjangoBulkMessageCampaignRepository()

        repository.create(campaign)
        stored = BulkMessageCampaignRecord.objects.get(id=campaign.id)
        loaded = repository.find_by_id(campaign.id)

        self.assertNotEqual(stored.template, content)
        self.assertTrue(stored.template.startswith("v1."))
        self.assertEqual(loaded.template, content)
        self.assertTrue(BulkMessageRecipientRecord.objects.filter(campaign_id=campaign.id).exists())

    def test_campaign_content_rotation_reencrypts_with_active_key(self):
        first_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        second_key = base64.urlsafe_b64encode(b"b" * 32).decode()
        campaign_id = uuid4()
        with override_settings(
            CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION="v1",
            CRM_MESSAGE_ENCRYPTION_KEYS={"v1": first_key},
        ):
            campaign = BulkMessageCampaign.create(
                merchant_id=uuid4(),
                segment_id=uuid4(),
                channel="whatsapp",
                template="campaign body",
                recipient_contact_ids=(),
                created_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
            )
            campaign.id = campaign_id
            DjangoBulkMessageCampaignRepository().create(campaign)

        output = StringIO()
        with override_settings(
            CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION="v2",
            CRM_MESSAGE_ENCRYPTION_KEYS={"v1": first_key, "v2": second_key},
        ):
            call_command("rotate_campaign_content", stdout=output)
            loaded = DjangoBulkMessageCampaignRepository().find_by_id(campaign_id)
            stored = BulkMessageCampaignRecord.objects.get(id=campaign_id)

        self.assertEqual(loaded.template, "campaign body")
        self.assertTrue(stored.template.startswith("v2."))
        self.assertEqual(output.getvalue(), "Rotated 1 CRM campaign template(s).\n")

    def test_legacy_plaintext_campaign_template_is_migrated_when_loaded(self):
        campaign_id = uuid4()
        content = "legacy campaign template"
        BulkMessageCampaignRecord.objects.create(
            id=campaign_id,
            merchant_id=uuid4(),
            segment_id=uuid4(),
            channel="whatsapp",
            template=content,
            status="processing",
            recipient_count=0,
            created_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        )

        loaded = DjangoBulkMessageCampaignRepository().find_by_id(campaign_id)
        stored = BulkMessageCampaignRecord.objects.get(id=campaign_id)

        self.assertEqual(loaded.template, content)
        self.assertTrue(stored.template.startswith("v1."))

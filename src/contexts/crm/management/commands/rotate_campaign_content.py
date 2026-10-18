from django.core.management.base import BaseCommand
from django.db import transaction

from contexts.crm.infrastructure.adapters.django_campaign_content_cipher import (
    DjangoCampaignContentCipher,
)
from contexts.crm.infrastructure.persistence.models import BulkMessageCampaignRecord


class Command(BaseCommand):
    """Rotate persisted campaign templates to the active CRM message key."""

    help = "Re-encrypt persisted CRM campaign templates with the active key version."

    def handle(self, *args, **options):
        """Rotate each campaign in an independent transaction and report only a count."""
        cipher = DjangoCampaignContentCipher()
        campaign_ids = BulkMessageCampaignRecord.objects.order_by("id").values_list("id", flat=True)
        rotated_count = 0
        for campaign_id in campaign_ids:
            with transaction.atomic():
                campaign = BulkMessageCampaignRecord.objects.select_for_update().get(id=campaign_id)
                if cipher.key_version(campaign.template) == cipher.active_version:
                    continue
                campaign.template = cipher.encrypt(cipher.decrypt(campaign.template))
                campaign.save(update_fields=["template"])
                rotated_count += 1
        self.stdout.write(f"Rotated {rotated_count} CRM campaign template(s).")
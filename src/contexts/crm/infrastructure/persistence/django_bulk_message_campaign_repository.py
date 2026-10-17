"""Module: contexts/crm/infrastructure/django_bulk_message_campaign_repository.py
Context: CRM.
Role: persist campaign audience snapshots and per-recipient delivery journals.
"""

from datetime import datetime, timezone
from uuid import UUID

from ...domain.entities.bulk_message_campaign import (
    BulkMessageCampaign,
    BulkMessageCampaignStatus,
)
from ...application.ports import IBulkMessageCampaignRepository
from ..persistence.models import BulkMessageCampaignRecord, BulkMessageRecipientRecord


class DjangoBulkMessageCampaignRepository(IBulkMessageCampaignRepository):
    """Persist campaign metadata and recipient statuses in CRM-owned tables."""

    def create(self, campaign: BulkMessageCampaign) -> None:
        """Insert campaign and its immutable audience journals in the caller transaction."""
        BulkMessageCampaignRecord.objects.create(
            id=campaign.id,
            merchant_id=campaign.merchant_id,
            segment_id=campaign.segment_id,
            channel=campaign.channel,
            template=campaign.template,
            status=campaign.status.value,
            recipient_count=len(campaign.recipient_contact_ids),
            created_at=campaign.created_at,
        )
        BulkMessageRecipientRecord.objects.bulk_create(
            [
                BulkMessageRecipientRecord(
                    campaign_id=campaign.id,
                    contact_id=contact_id,
                    status="queued",
                )
                for contact_id in campaign.recipient_contact_ids
            ]
        )

    def find_by_id(self, campaign_id: UUID) -> BulkMessageCampaign | None:
        """Load campaign metadata and the frozen recipient ID snapshot."""
        record = BulkMessageCampaignRecord.objects.filter(id=campaign_id).first()
        if record is None:
            return None
        recipient_ids = tuple(
            BulkMessageRecipientRecord.objects.filter(campaign_id=campaign_id)
            .order_by("contact_id")
            .values_list("contact_id", flat=True)
        )
        return BulkMessageCampaign(
            id=record.id,
            merchant_id=record.merchant_id,
            segment_id=record.segment_id,
            channel=record.channel,
            template=record.template,
            recipient_contact_ids=recipient_ids,
            created_at=record.created_at,
            status=BulkMessageCampaignStatus(record.status),
        )

    def find_pending_contact_ids(self, campaign_id: UUID) -> list[UUID]:
        """List queued recipients in stable order for resumable processing."""
        return list(
            BulkMessageRecipientRecord.objects.filter(
                campaign_id=campaign_id,
                status="queued",
            )
            .order_by("contact_id")
            .values_list("contact_id", flat=True)
        )

    def mark_sent(self, campaign_id: UUID, contact_id: UUID) -> None:
        """Mark only a still-queued recipient sent; repeated completion is harmless."""
        BulkMessageRecipientRecord.objects.filter(
            campaign_id=campaign_id,
            contact_id=contact_id,
            status="queued",
        ).update(status="sent", sent_at=datetime.now(timezone.utc), failure_code=None)

    def mark_failed(self, campaign_id: UUID, contact_id: UUID, failure_code: str) -> None:
        """Persist a terminal failure code without storing message body or exception text."""
        BulkMessageRecipientRecord.objects.filter(
            campaign_id=campaign_id,
            contact_id=contact_id,
            status="queued",
        ).update(status="failed", failure_code=failure_code)

    def counts(self, campaign_id: UUID) -> tuple[int, int, int]:
        """Count terminal and queued recipient journals for campaign progress."""
        records = BulkMessageRecipientRecord.objects.filter(campaign_id=campaign_id)
        return (
            records.filter(status="sent").count(),
            records.filter(status="failed").count(),
            records.filter(status="queued").count(),
        )

    def complete(self, campaign_id: UUID) -> BulkMessageCampaign | None:
        """Mark one campaign complete only when every recipient has a terminal state."""
        record = BulkMessageCampaignRecord.objects.select_for_update().filter(
            id=campaign_id
        ).first()
        if record is None or record.status == BulkMessageCampaignStatus.COMPLETED.value:
            return None
        if BulkMessageRecipientRecord.objects.filter(
            campaign_id=campaign_id,
            status="queued",
        ).exists():
            return None
        completed_at = datetime.now(timezone.utc)
        record.status = BulkMessageCampaignStatus.COMPLETED.value
        record.completed_at = completed_at
        record.save(update_fields=["status", "completed_at"])
        return self.find_by_id(campaign_id)
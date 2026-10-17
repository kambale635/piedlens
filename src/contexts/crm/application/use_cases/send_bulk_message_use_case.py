from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ...domain.entities.bulk_message_campaign import BulkMessageCampaign
from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.repositories.i_segment_repository import ISegmentRepository
from ...domain.services.segment_membership_calculator import SegmentMembershipCalculator
from ...domain.events.crm_events import BulkMessageQueued
from ..exceptions import BulkMessageChannelException, SegmentNotFoundException
from ..ports import IBulkMessageCampaignRepository, ICRMOutbox, ICRMUnitOfWork


@dataclass(frozen=True)
class SendBulkMessageResult:
    """Acknowledgement for a campaign durably queued for asynchronous delivery."""

    bulk_message_log_id: UUID
    status: str
    recipient_count: int


class SendBulkMessageUseCase:
    """Snapshot a dynamic audience and queue a durable CRM message campaign.

    Contract: docs/15-use-cases-catalog.md#contexte-crm.
    The supplied template is already rendered; this Use Case performs no external
    delivery and writes the campaign, recipient journal, and Outbox event atomically.

    Args:
        segment_repository: CRM-owned dynamic segment definitions.
        contact_repository: CRM-owned Contacts used to resolve the audience snapshot.
        campaign_repository: persistence port for campaign and recipient journals.
        unit_of_work: CRM transaction for campaign and Outbox creation.
        outbox: CRM Outbox shared with the campaign transaction.

    Returns:
        Campaign ID, `processing` status, and the immutable recipient count.

    Raises:
        SegmentNotFoundException: when the requested segment is absent.
        BulkMessageChannelException: when the channel is outside the CRM contract.

    Protects INV-TR-01/02.
    """

    SUPPORTED_CHANNELS = frozenset({"whatsapp", "instagram"})

    def __init__(
        self,
        segment_repository: ISegmentRepository,
        contact_repository: IContactRepository,
        campaign_repository: IBulkMessageCampaignRepository,
        unit_of_work: ICRMUnitOfWork,
        outbox: ICRMOutbox,
    ) -> None:
        """Receive CRM repositories, UnitOfWork, and Outbox through ports."""
        self._segment_repository = segment_repository
        self._contact_repository = contact_repository
        self._campaign_repository = campaign_repository
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._membership_calculator = SegmentMembershipCalculator()

    def execute(
        self,
        segment_id: UUID,
        template: str,
        channel: str,
        merchant_id: UUID | None = None,
    ) -> SendBulkMessageResult:
        """Persist one campaign and publish its queue request without sending inline."""
        if channel not in self.SUPPORTED_CHANNELS:
            raise BulkMessageChannelException("Unsupported bulk message channel.")
        segment = self._segment_repository.find_by_id(segment_id)
        if segment is None or (merchant_id is not None and segment.merchant_id != merchant_id):
            raise SegmentNotFoundException("CRM segment was not found.")

        contacts = self._contact_repository.find_by_merchant(segment.merchant_id)
        members = self._membership_calculator.evaluate(segment.definition_rule, contacts)
        campaign = BulkMessageCampaign.create(
            merchant_id=segment.merchant_id,
            segment_id=segment.id,
            channel=channel,
            template=template,
            recipient_contact_ids=tuple(contact.id for contact in members),
            created_at=datetime.now(timezone.utc),
        )
        event = BulkMessageQueued(
            event_id=uuid4(),
            occurred_at=campaign.created_at,
            merchant_id=campaign.merchant_id,
            campaign_id=campaign.id,
            recipient_count=len(campaign.recipient_contact_ids),
        )
        with self._unit_of_work:
            self._campaign_repository.create(campaign)
            self._outbox.add(event)

        return SendBulkMessageResult(
            bulk_message_log_id=campaign.id,
            status=campaign.status.value,
            recipient_count=len(campaign.recipient_contact_ids),
        )

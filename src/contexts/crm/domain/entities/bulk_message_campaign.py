from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class BulkMessageCampaignStatus(StrEnum):
    """Lifecycle state for one durable CRM bulk-message campaign."""

    PROCESSING = "processing"
    COMPLETED = "completed"


@dataclass
class BulkMessageCampaign:
    """Aggregate root for a durable campaign and its immutable audience snapshot.

    Campaign metadata and the recipient snapshot are persisted atomically with
    `BulkMessageQueued`; recipient delivery logs are updated in independent
    transactions. Completion and `BulkMessageCompleted` are committed together
    (INV-TR-01/02/03).
    """

    id: UUID
    merchant_id: UUID
    segment_id: UUID
    channel: str
    template: str
    recipient_contact_ids: tuple[UUID, ...]
    created_at: datetime
    status: BulkMessageCampaignStatus = BulkMessageCampaignStatus.PROCESSING

    @classmethod
    def create(
        cls,
        merchant_id: UUID,
        segment_id: UUID,
        channel: str,
        template: str,
        recipient_contact_ids: tuple[UUID, ...],
        created_at: datetime,
    ) -> "BulkMessageCampaign":
        """Create a campaign with an immutable snapshot of the resolved audience."""
        return cls(
            id=uuid4(),
            merchant_id=merchant_id,
            segment_id=segment_id,
            channel=channel,
            template=template,
            recipient_contact_ids=recipient_contact_ids,
            created_at=created_at,
        )

    def complete(self, pending_count: int) -> None:
        """Complete only after every audience member has a terminal delivery result."""
        if pending_count != 0:
            raise ValueError("A campaign cannot complete while recipients are pending.")
        self.status = BulkMessageCampaignStatus.COMPLETED
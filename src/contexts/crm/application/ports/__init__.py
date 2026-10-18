from typing import Protocol
from uuid import UUID

from ...domain.entities.bulk_message_campaign import BulkMessageCampaign
from ...domain.value_objects.relationship_anomaly_policy import RelationshipAnomalyPolicy


class ICRMUnitOfWork(Protocol):
    """Transaction boundary for one CRM aggregate and its consumer ledger marker."""

    def __enter__(self) -> "ICRMUnitOfWork":
        """Begin the CRM database transaction."""

    def __exit__(self, exception_type, exception, traceback) -> bool | None:
        """Commit on success or roll back all CRM writes on failure."""


class IProcessedMessageRepository(Protocol):
    """Idempotency ledger for the CRM MessageReceived consumer (INV-TR-03)."""

    def has_processed(self, event_id: UUID, consumer_name: str) -> bool:
        """Check the event/consumer key before applying a message event."""

    def mark_processed(self, event_id: UUID, consumer_name: str) -> None:
        """Write the marker in the Contact transaction."""


class ICRMOutbox(Protocol):
    """CRM-owned port for transactional producer events (INV-TR-02)."""

    def add(self, event: object) -> None:
        """Append one event to the active CRM database transaction."""


class ICRMMerchantPurger(Protocol):
    """Local persistence port for resumable merchant deletion (INV-CRM-09)."""

    def purge_merchant_data(self, event_id: UUID, merchant_id: UUID) -> None: ...


class IRelationshipAnomalyConfiguration(Protocol):
    """Resolve configured anomaly thresholds for one merchant (INV-CRM-05)."""

    def for_merchant(self, merchant_id: UUID) -> RelationshipAnomalyPolicy:
        """Return settings defaults with any configured merchant override."""


class ICRMClock(Protocol):
    """Application clock port for deterministic CRM scheduled jobs."""

    def now_utc(self):
        """Return the current timezone-aware UTC instant."""


class ICRMSegmentMembershipCache(Protocol):
    """Ephemeral cache port for paginated dynamic CRM segment membership."""

    def get_members(
        self,
        segment_id: UUID,
        merchant_id: UUID,
        page: int,
        page_size: int,
    ) -> dict | None:
        """Return a cached result for this segment page, if present."""

    def set_members(
        self,
        segment_id: UUID,
        merchant_id: UUID,
        page: int,
        page_size: int,
        result: dict,
    ) -> None:
        """Cache a page for the configured short TTL."""

    def invalidate_merchant(self, merchant_id: UUID) -> None:
        """Invalidate all membership pages affected by a merchant Contact update."""


class ICRMRateLimiter(Protocol):
    """Rate-limit outgoing campaigns by platform channel."""

    def check_allowed(self, channel: str) -> bool:
        """Return whether one outgoing message may be sent now."""


class ICRMMessageSender(Protocol):
    """Platform delivery port with a stable idempotency key for retries."""

    def send_message(
        self,
        channel: str,
        contact,
        template: str,
        idempotency_key: str,
    ):
        """Send one pre-rendered message and return its delivery outcome."""


class IBulkMessageCampaignRepository(Protocol):
    """Persistence port for campaigns and per-recipient delivery journals."""

    def create(self, campaign: BulkMessageCampaign) -> None:
        """Persist a campaign and its queued audience snapshot in the caller transaction."""

    def find_by_id(self, campaign_id: UUID) -> BulkMessageCampaign | None:
        """Load campaign metadata and its immutable audience snapshot."""

    def find_pending_contact_ids(self, campaign_id: UUID) -> list[UUID]:
        """Return recipients whose delivery result is not terminal."""

    def mark_sent(self, campaign_id: UUID, contact_id: UUID) -> None:
        """Mark one recipient delivered in its own transaction."""

    def mark_failed(self, campaign_id: UUID, contact_id: UUID, failure_code: str) -> None:
        """Mark one recipient failed without storing message content."""

    def counts(self, campaign_id: UUID) -> tuple[int, int, int]:
        """Return sent, failed, and pending recipient counts."""

    def complete(self, campaign_id: UUID) -> BulkMessageCampaign | None:
        """Mark the campaign completed when its recipient journals are terminal."""


class ICRMRateLimiter(Protocol):
    """Rate-limit outgoing campaigns by platform channel."""

    def check_allowed(self, channel: str) -> bool:
        """Return whether one outgoing message may be sent now."""


class ICRMMessageSender(Protocol):
    """Platform delivery port with a stable idempotency key for retries."""

    def send_message(
        self,
        channel: str,
        contact,
        template: str,
        idempotency_key: str,
    ):
        """Send one pre-rendered message and return its delivery result."""
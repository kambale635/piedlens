from dataclasses import dataclass
from datetime import datetime, timezone
import re
from urllib.parse import quote
from uuid import UUID, uuid4

from shared_kernel.application_exceptions import (
    OutboundRateMissingException,
    PlanUpgradeRequiredException,
    ValidationException,
)
from shared_kernel.ports import (
    IEntitlementReader,
    IMerchantCurrencyReader,
    IOutboundCostEstimator,
)

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
    manual_links: tuple[dict[str, str], ...] = ()
    cost_estimate: dict[str, object] | None = None


class MarketingConfirmationRequiredException(ValidationException):
    error_code = "MARKETING_CONFIRMATION_REQUIRED"


class ManualLinkRecipientUnavailableException(ValidationException):
    error_code = "MANUAL_LINK_RECIPIENT_UNAVAILABLE"


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
    SUPPORTED_CATEGORIES = frozenset(
        {"service", "utility", "marketing", "authentication"}
    )

    def __init__(
        self,
        segment_repository: ISegmentRepository,
        contact_repository: IContactRepository,
        campaign_repository: IBulkMessageCampaignRepository,
        unit_of_work: ICRMUnitOfWork,
        outbox: ICRMOutbox,
        entitlements: IEntitlementReader,
        cost_estimator: IOutboundCostEstimator,
        merchant_country_reader,
        merchant_currency_reader: IMerchantCurrencyReader,
    ) -> None:
        """Receive CRM repositories, UnitOfWork, and Outbox through ports."""
        self._segment_repository = segment_repository
        self._contact_repository = contact_repository
        self._campaign_repository = campaign_repository
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._entitlements = entitlements
        self._cost_estimator = cost_estimator
        self._merchant_country_reader = merchant_country_reader
        self._merchant_currency_reader = merchant_currency_reader
        self._membership_calculator = SegmentMembershipCalculator()

    def execute(
        self,
        segment_id: UUID,
        template: str,
        channel: str,
        merchant_id: UUID | None = None,
        delivery_mode: str = "manual_link",
        category: str = "marketing",
        marketing_confirmed: bool = False,
        confirmed_estimate: dict[str, object] | None = None,
    ) -> SendBulkMessageResult:
        """Persist one campaign and publish its queue request without sending inline."""
        if channel not in self.SUPPORTED_CHANNELS:
            raise BulkMessageChannelException("Unsupported bulk message channel.")
        if delivery_mode not in {"manual_link", "api_send"}:
            raise BulkMessageChannelException("Unsupported outbound delivery mode.")
        if delivery_mode == "manual_link" and channel != "whatsapp":
            raise BulkMessageChannelException("Manual link delivery is available only for WhatsApp.")
        if category not in self.SUPPORTED_CATEGORIES:
            raise BulkMessageChannelException("Unsupported outbound message category.")
        entitlements = self._entitlements.entitlements_for(merchant_id)
        if entitlements.get("bulk_messages") is not True:
            raise PlanUpgradeRequiredException("bulk_messages")
        allowed_modes = entitlements.get("reminder_modes", [])
        if delivery_mode not in allowed_modes:
            raise PlanUpgradeRequiredException("reminder_modes")
        segment = self._segment_repository.find_by_id(segment_id)
        if segment is None or (merchant_id is not None and segment.merchant_id != merchant_id):
            raise SegmentNotFoundException("CRM segment was not found.")

        contacts = self._contact_repository.find_by_merchant(segment.merchant_id)
        members = self._membership_calculator.evaluate(segment.definition_rule, contacts)
        manual_links: tuple[dict[str, str], ...] = ()
        cost_estimate = None
        if delivery_mode == "manual_link":
            links = []
            for contact in members:
                recipient = contact.external_identifier
                if not re.fullmatch(r"[1-9][0-9]{7,14}", recipient):
                    raise ManualLinkRecipientUnavailableException(
                        "Contact has no international phone number usable for a WhatsApp link."
                    )
                links.append(
                    {
                        "contactId": str(contact.id),
                        "url": f"https://wa.me/{recipient}?text={quote(template)}",
                    }
                )
            manual_links = tuple(links)
        else:
            if category == "marketing" and not marketing_confirmed:
                raise MarketingConfirmationRequiredException(
                    "Marketing delivery requires explicit cost confirmation."
                )
            if members:
                country = self._merchant_country_reader.country_code_for(segment.merchant_id)
                if country is None:
                    raise ValidationException("Merchant country is not configured.")
                cost_estimate = self._cost_estimator.estimate(
                    country,
                    self._merchant_currency_reader.currency_for(segment.merchant_id),
                    category,
                    len(members),
                )
                if cost_estimate is None:
                    raise OutboundRateMissingException(
                        "No active outbound rate is configured for this message."
                    )
                if category == "marketing" and confirmed_estimate != cost_estimate:
                    raise MarketingConfirmationRequiredException(
                        "Confirm the current estimated cost before sending marketing messages."
                    )
        campaign = BulkMessageCampaign.create(
            merchant_id=segment.merchant_id,
            segment_id=segment.id,
            channel=channel,
            delivery_mode=delivery_mode,
            category=category,
            cost_estimate=cost_estimate,
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
            manual_links=manual_links,
            cost_estimate=cost_estimate,
        )

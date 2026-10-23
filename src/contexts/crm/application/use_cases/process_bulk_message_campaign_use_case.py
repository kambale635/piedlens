from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared_kernel.application_exceptions import (
	OutboundQuotaExceededException,
	OutboundRateMissingException,
)
from shared_kernel.ports import (
	IOutboundCostEstimator,
	IMerchantCountryReader,
	IMerchantCurrencyReader,
	IOutboundUsageRecorder,
)

from ...domain.entities.bulk_message_campaign import BulkMessageCampaignStatus
from ...domain.value_objects.contact_status import ContactStatus
from ...domain.repositories.i_contact_repository import IContactRepository
from ...domain.events.crm_events import BulkMessageCompleted
from ..exceptions import BulkMessageCampaignNotFoundException
from ..ports import (
	IBulkMessageCampaignRepository,
	ICRMMessageSender,
	ICRMOutbox,
	ICRMRateLimiter,
	ICRMUnitOfWork,
	IProcessedMessageRepository,
)


@dataclass(frozen=True)
class BulkMessageDeliveryResult:
	"""Terminal outcome from one platform sender call, without message content."""

	succeeded: bool
	failure_code: str | None = None


@dataclass(frozen=True)
class ProcessBulkMessageCampaignResult:
	"""Progress counters for one attempt to process a durable campaign."""

	status: str
	sent_count: int
	failed_count: int
	pending_count: int
	proposed_count: int


class ProcessBulkMessageCampaignUseCase:
	"""Deliver queued recipients independently and finalize the campaign atomically.

	Trigger: CRM `BulkMessageQueued`; contract:
	docs/15-use-cases-catalog.md#contexte-crm.
	Each recipient journal is updated in its own CRM transaction. External delivery
	happens outside SQL transactions and uses a stable campaign/contact idempotency
	key; rate-limited recipients remain queued. Campaign completion, Outbox event,
	and processed-event marker commit together (INV-TR-01/02/03).

	Args:
		campaign_repository: CRM campaign and per-recipient journal persistence.
		contact_repository: CRM-owned Contact lookup for the frozen audience IDs.
		processed_events: idempotency ledger for the campaign queue event.
		rate_limiter: injected platform/channel rate-limit policy.
		message_sender: injected sender that deduplicates the supplied idempotency key.
		unit_of_work: CRM transaction boundary for recipient and completion writes.
		outbox: transactional Outbox for `BulkMessageCompleted`.

	Returns:
		Current status and sent, failed, and pending recipient counts.

	Raises:
		BulkMessageCampaignNotFoundException: if the queued campaign is absent.
		Infrastructure exceptions propagate for event retry/dead-letter handling.

	Protects INV-TR-01/02/03.
	"""

	CONSUMER_NAME = "crm-bulk-message-consumer"

	def __init__(
		self,
		campaign_repository: IBulkMessageCampaignRepository,
		contact_repository: IContactRepository,
		processed_events: IProcessedMessageRepository,
		rate_limiter: ICRMRateLimiter,
		message_sender: ICRMMessageSender,
		unit_of_work: ICRMUnitOfWork,
		outbox: ICRMOutbox,
		outbound_usage: IOutboundUsageRecorder,
		outbound_cost_estimator: IOutboundCostEstimator,
		merchant_country_reader: IMerchantCountryReader,
		merchant_currency_reader: IMerchantCurrencyReader,
	) -> None:
		"""Receive campaign, Contact, idempotency, delivery, and transaction ports."""
		self._campaign_repository = campaign_repository
		self._contact_repository = contact_repository
		self._processed_events = processed_events
		self._rate_limiter = rate_limiter
		self._message_sender = message_sender
		self._unit_of_work = unit_of_work
		self._outbox = outbox
		self._outbound_usage = outbound_usage
		self._outbound_cost_estimator = outbound_cost_estimator
		self._merchant_country_reader = merchant_country_reader
		self._merchant_currency_reader = merchant_currency_reader

	def execute(
		self,
		event_id: UUID,
		campaign_id: UUID,
	) -> ProcessBulkMessageCampaignResult:
		"""Resume queued recipients and finalize only after all have terminal results."""
		with self._unit_of_work:
			if self._processed_events.has_processed(event_id, self.CONSUMER_NAME):
				return self._result(campaign_id)
			campaign = self._campaign_repository.find_by_id(campaign_id)
			if campaign is None:
				raise BulkMessageCampaignNotFoundException("Bulk message campaign was not found.")
			pending_contact_ids = self._campaign_repository.find_pending_contact_ids(campaign_id)

		for contact_id in pending_contact_ids:
			if campaign.delivery_mode == "manual_link":
				with self._unit_of_work:
					self._campaign_repository.mark_manual_link(campaign_id, contact_id)
				continue
			if not self._rate_limiter.check_allowed(campaign.channel):
				break
			contact = self._contact_repository.find_by_id(contact_id)
			if contact is None:
				delivery_result = BulkMessageDeliveryResult(False, "CONTACT_NOT_FOUND")
			elif contact.status is ContactStatus.MERGED:
				delivery_result = BulkMessageDeliveryResult(False, "CONTACT_MERGED")
			else:
				idempotency_key = f"{campaign.id}:{contact_id}"
				country = self._merchant_country_reader.country_code_for(
					campaign.merchant_id
				)
				currency = self._merchant_currency_reader.currency_for(
					campaign.merchant_id
				)
				rate = self._outbound_cost_estimator.estimate(
					country, currency, campaign.category, 1
				)
				if rate is None:
					raise OutboundRateMissingException(
						"No active outbound rate is configured for this message."
					)
				try:
					self._outbound_usage.reserve(
						campaign.merchant_id, campaign.category, idempotency_key
					)
				except OutboundQuotaExceededException:
					break
				delivery_result = self._message_sender.send_message(
					channel=campaign.channel,
					contact=contact,
					template=campaign.template,
					idempotency_key=idempotency_key,
				)

			with self._unit_of_work:
				if delivery_result.succeeded:
					self._campaign_repository.mark_sent(campaign_id, contact_id)
				else:
					self._campaign_repository.mark_failed(
						campaign_id,
						contact_id,
						delivery_result.failure_code or "DELIVERY_FAILED",
					)

		with self._unit_of_work:
			sent_count, failed_count, pending_count, proposed_count = self._campaign_repository.counts(
				campaign_id
			)
			if pending_count == 0 and not self._processed_events.has_processed(
				event_id,
				self.CONSUMER_NAME,
			):
				completed_campaign = self._campaign_repository.complete(campaign_id)
				if completed_campaign is not None:
					self._outbox.add(
						BulkMessageCompleted(
							event_id=uuid4(),
							occurred_at=datetime.now(timezone.utc),
							merchant_id=completed_campaign.merchant_id,
							campaign_id=campaign_id,
							sent_count=sent_count,
							failed_count=failed_count,
						)
					)
				self._processed_events.mark_processed(event_id, self.CONSUMER_NAME)
				return ProcessBulkMessageCampaignResult(
					status=BulkMessageCampaignStatus.COMPLETED.value,
					sent_count=sent_count,
					failed_count=failed_count,
					pending_count=0,
					proposed_count=proposed_count,
				)

		return self._result(campaign_id)

	def _result(self, campaign_id: UUID) -> ProcessBulkMessageCampaignResult:
		"""Read counters for a redelivery or rate-limited partial campaign."""
		campaign = self._campaign_repository.find_by_id(campaign_id)
		if campaign is None:
			raise BulkMessageCampaignNotFoundException("Bulk message campaign was not found.")
		sent_count, failed_count, pending_count, proposed_count = self._campaign_repository.counts(
			campaign_id
		)
		return ProcessBulkMessageCampaignResult(
			status=campaign.status.value,
			sent_count=sent_count,
			failed_count=failed_count,
			pending_count=pending_count,
			proposed_count=proposed_count,
		)
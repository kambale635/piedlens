from __future__ import annotations

from uuid import UUID

from ..domain.contact import Contact
from ..domain.i_contact_repository import IContactRepository
from ..domain.i_segment_repository import ISegmentRepository
from ..domain.segment_membership_calculator import SegmentMembershipCalculator


class SendBulkMessageUseCase:
    """Send a templated bulk message to each contact in a CRM segment.

    The use case integrates the dynamic segment evaluation with external message
    sending under the platform rate-limiter contract. The business rule is
    intentionally kept in the application layer, while the actual platform API
    dependency is injected through ports.
    """

    def __init__(
        self,
        segment_repository: ISegmentRepository,
        contact_repository: IContactRepository,
        rate_limiter,
        message_sender,
    ) -> None:
        """Inject the segment, contact, rate-limit, and message-sending ports."""
        self._segment_repository = segment_repository
        self._contact_repository = contact_repository
        self._rate_limiter = rate_limiter
        self._message_sender = message_sender
        self._membership_calculator = SegmentMembershipCalculator()

    def execute(
        self,
        segment_id: UUID,
        template: str,
        channel: str,
    ) -> dict:
        """Resolve the segment, check quota, and send the same template to each member."""
        segment = self._segment_repository.find_by_id(segment_id)
        if segment is None:
            return {"status": "processing", "recipient_count": 0}

        contacts = self._contact_repository.find_by_merchant(segment.merchant_id)
        members = self._membership_calculator.evaluate(segment.definition_rule, contacts)

        for contact in members:
            self._rate_limiter.check_allowed(channel)
            self._message_sender.send_message(channel=channel, contact=contact, template=template)

        return {
            "status": "processing",
            "recipient_count": len(members),
        }

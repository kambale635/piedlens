from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared_kernel.value_objects.confidence_score import ConfidenceScore
from shared_kernel.value_objects.money import Money

from ..exceptions.order_detection_exceptions import InvalidOrderTransitionException
from ..value_objects.order_status import OrderStatus


@dataclass
class Order:
    """Represents a detected purchase and protects its lifecycle and amount.

    Order is the Aggregate Root of Order Detection. Status changes must pass
    through `change_status()` (INV-OD-01); amount signals are recorded in message
    order so the latest detected amount is retained (INV-OD-03). Every amount is
    a shared Money value object (INV-OD-05).

    See docs/11-context-order-detection.md and docs/02-domain-model.md.
    """

    id: UUID
    merchant_id: UUID
    contact_id: UUID
    source_candidate_id: UUID | None
    _detected_amount: Money
    confidence_score: ConfidenceScore
    _source_message_ids: list[UUID]
    _status: OrderStatus
    _created_at: datetime
    _last_status_change_at: datetime
    _recorded_amount_message_ids: set[UUID] = field(default_factory=set, repr=False)
    _latest_amount_at: datetime | None = field(default=None, repr=False)

    @classmethod
    def detect(
        cls,
        merchant_id: UUID,
        contact_id: UUID,
        detected_amount: Money,
        confidence_score: ConfidenceScore,
        source_message_id: UUID,
        occurred_at: datetime | None = None,
        source_candidate_id: UUID | None = None,
    ) -> "Order":
        """Create an Order only after the application has checked INV-OD-04."""
        detected_at = occurred_at or datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            merchant_id=merchant_id,
            contact_id=contact_id,
            source_candidate_id=source_candidate_id,
            _detected_amount=detected_amount,
            confidence_score=confidence_score,
            _source_message_ids=[source_message_id],
            _status=OrderStatus.PENDING_PAYMENT,
            _created_at=detected_at,
            _last_status_change_at=detected_at,
            _recorded_amount_message_ids={source_message_id},
            _latest_amount_at=detected_at,
        )

    def change_status(
        self, new_status: OrderStatus, occurred_at: datetime | None = None
    ) -> None:
        """Change status only along the permitted state graph (INV-OD-01).

        Raises:
            InvalidOrderTransitionException: when the requested transition is invalid.
        """
        allowed_transitions = {
            OrderStatus.PENDING_PAYMENT: {
                OrderStatus.PAID_NOT_DELIVERED,
                OrderStatus.CANCELLED,
            },
            OrderStatus.PAID_NOT_DELIVERED: {
                OrderStatus.PAID_AND_DELIVERED,
                OrderStatus.CANCELLED,
            },
            OrderStatus.PAID_AND_DELIVERED: set(),
            OrderStatus.CANCELLED: set(),
        }
        if new_status not in allowed_transitions[self._status]:
            raise InvalidOrderTransitionException(self._status.value, new_status.value)

        self._status = new_status
        self._last_status_change_at = occurred_at or datetime.now(timezone.utc)

    def record_amount_signal(
        self, amount: Money, source_message_id: UUID, source_message_timestamp: datetime
    ) -> None:
        """Record a newer amount-bearing message, protecting INV-OD-02/03/05."""
        if self._status not in {
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PAID_NOT_DELIVERED,
        }:
            return
        if source_message_id in self._recorded_amount_message_ids:
            return

        self._recorded_amount_message_ids.add(source_message_id)
        self._source_message_ids.append(source_message_id)
        if self._latest_amount_at is None or source_message_timestamp > self._latest_amount_at:
            self._detected_amount = amount
            self._latest_amount_at = source_message_timestamp

    def reassign_contact(self, contact_id: UUID) -> None:
        """Reassign this Order after a CRM Contact merge (INV-CRM-03, INV-TR-01)."""
        self.contact_id = contact_id

    @property
    def detected_amount(self) -> Money:
        """Return the current amount without allowing mutation outside the aggregate."""
        return self._detected_amount

    @property
    def source_message_ids(self) -> tuple[UUID, ...]:
        """Return source message identifiers as an immutable snapshot."""
        return tuple(self._source_message_ids)

    @property
    def status(self) -> OrderStatus:
        """Return the lifecycle state protected by `change_status()` (INV-OD-01)."""
        return self._status

    @property
    def created_at(self) -> datetime:
        """Return the immutable creation timestamp used for correlation ordering."""
        return self._created_at

    @property
    def last_status_change_at(self) -> datetime:
        """Return the timestamp of the last valid state transition."""
        return self._last_status_change_at

    @property
    def latest_amount_at(self) -> datetime | None:
        """Return the source-message time for the amount currently retained."""
        return self._latest_amount_at
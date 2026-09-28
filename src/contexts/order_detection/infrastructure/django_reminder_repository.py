"""Module: contexts/order_detection/infrastructure/django_reminder_repository.py
Context: Order Detection.
Role: persist scheduled Reminder aggregates and enforce INV-OD-06 in PostgreSQL.
"""

from datetime import datetime
from uuid import UUID

from django.db import IntegrityError
from django.db.models import Q

from ..application.reminder_exceptions import ReminderAlreadyScheduledException
from ..domain.i_reminder_repository import IReminderRepository
from ..domain.reminder import Reminder, ReminderStatus, ReminderType
from .models import ReminderRecord


class DjangoReminderRepository(IReminderRepository):
    """Implement Reminder persistence using the active Django transaction."""

    def has_scheduled(self, order_id: UUID, reminder_type: ReminderType) -> bool:
        """Check for an active duplicate; the conditional DB constraint closes races."""
        return ReminderRecord.objects.filter(
            order_id=order_id,
            reminder_type=reminder_type.value,
            status__in=[ReminderStatus.SCHEDULED.value, ReminderStatus.PROCESSING.value],
        ).exists()

    def find_by_id(self, reminder_id: UUID) -> Reminder | None:
        """Reload a reminder after its row has been locked by the UnitOfWork."""
        record = ReminderRecord.objects.filter(id=reminder_id).first()
        return self._to_domain(record) if record else None

    def save(self, reminder: Reminder) -> None:
        """Insert or update a Reminder inside the caller's UnitOfWork."""
        try:
            ReminderRecord.objects.update_or_create(
                id=reminder.id,
                defaults={
                    "order_id": reminder.order_id,
                    "reminder_type": reminder.reminder_type.value,
                    "status": reminder.status.value,
                    "scheduled_for": reminder.scheduled_for,
                    "custom_message": reminder.custom_message,
                    "attempt_count": reminder.attempt_count,
                    "lease_until": reminder.lease_until,
                    "lease_token": reminder.lease_token,
                    "next_attempt_at": reminder.next_attempt_at,
                },
            )
        except IntegrityError as error:
            cause = error.__cause__
            constraint_name = getattr(getattr(cause, "diag", None), "constraint_name", None)
            if (
                constraint_name == "uniq_scheduled_reminder_order_type"
                or "uniq_scheduled_reminder_order_type" in str(error)
            ):
                raise ReminderAlreadyScheduledException(
                    "A reminder of this type is already scheduled for the Order."
                ) from error
            raise

    def claim_due(
        self,
        now: datetime,
        lease_until: datetime,
        limit: int,
    ) -> list[Reminder]:
        """Claim due reminders with row locks; reclaim expired worker leases."""
        due_scheduled = Q(
            status=ReminderStatus.SCHEDULED.value,
            scheduled_for__lte=now,
        ) & (Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        expired_processing = Q(
            status=ReminderStatus.PROCESSING.value,
            lease_until__lte=now,
        )
        records = list(
            ReminderRecord.objects.select_for_update(skip_locked=True)
            .filter(due_scheduled | expired_processing)
            .order_by("scheduled_for", "id")[:limit]
        )
        reminders = [self._to_domain(record) for record in records]
        for reminder, record in zip(reminders, records):
            reminder.claim(lease_until)
            record.status = reminder.status.value
            record.lease_until = reminder.lease_until
            record.lease_token = reminder.lease_token
            record.save(update_fields=["status", "lease_until", "lease_token"])
        return reminders

    @staticmethod
    def _to_domain(record: ReminderRecord) -> Reminder:
        """Rehydrate one Reminder aggregate without exposing its ORM record."""
        return Reminder(
            id=record.id,
            order_id=record.order_id,
            reminder_type=ReminderType(record.reminder_type),
            scheduled_for=record.scheduled_for,
            custom_message=record.custom_message,
            _status=ReminderStatus(record.status),
            attempt_count=record.attempt_count,
            lease_until=record.lease_until,
            lease_token=record.lease_token,
            next_attempt_at=record.next_attempt_at,
        )
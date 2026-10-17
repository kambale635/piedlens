"""Module: contexts/order_detection/infrastructure/django_unit_of_work.py
Context: Order Detection.
Role: implement atomic PostgreSQL transactions and candidate-level row locking.
"""

from django.db import transaction

from .models import (
    CandidateOrderCreationLockRecord,
    DetectionContactLockRecord,
    OrderRecord,
    ReminderRecord,
)


class DjangoOrderDetectionUnitOfWork:
    """Provide the concrete atomic transaction used by Order Detection use cases.

    Aggregate writes and `outbox_events`/`processed_events` operations issued while
    this context is active share Django's current database connection and transaction.
    This is the infrastructure implementation of INV-TR-01/02/03.
    """

    def __init__(self, atomic_factory=transaction.atomic) -> None:
        """Allow atomic transaction construction to be replaced in isolated tests."""
        self._atomic_factory = atomic_factory
        self._atomic_context = None

    def __enter__(self) -> "DjangoOrderDetectionUnitOfWork":
        """Open an ACID transaction on the configured Django database."""
        self._atomic_context = self._atomic_factory()
        self._atomic_context.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback) -> bool | None:
        """Commit on success and roll back all writes when an exception escapes."""
        return self._atomic_context.__exit__(exception_type, exception, traceback)

    def lock_candidate_creation(self, candidate_id) -> None:
        """Serialize concurrent deliveries for one candidate until transaction end."""
        CandidateOrderCreationLockRecord.objects.get_or_create(candidate_id=candidate_id)
        CandidateOrderCreationLockRecord.objects.select_for_update().get(
            candidate_id=candidate_id
        )

    def lock_order(self, order_id) -> None:
        """Lock an existing Order row until its status transaction commits."""
        OrderRecord.objects.select_for_update().filter(id=order_id).first()

    def lock_detection_contact(self, contact_id) -> None:
        """Serialize detection/correlation operations even when no Order exists yet."""
        DetectionContactLockRecord.objects.get_or_create(contact_id=contact_id)
        DetectionContactLockRecord.objects.select_for_update().get(contact_id=contact_id)

    def lock_reminder(self, reminder_id) -> None:
        """Lock one Reminder while its external delivery result is finalized."""
        ReminderRecord.objects.select_for_update().filter(id=reminder_id).first()
"""Module: contexts/crm/infrastructure/django_unit_of_work.py
Context: CRM.
Role: implement ACID transactions for Contact updates and processed-event markers.
"""

from django.db import transaction


class DjangoCRMUnitOfWork:
    """Wrap Contact, notification, processed-event and Outbox writes atomically.

    All CRM ORM adapters use Django's active default connection, so Outbox rows
    added inside this boundary commit or roll back with the associated business write
    (INV-TR-02/03).
    """

    def __init__(self, atomic_factory=transaction.atomic) -> None:
        """Accept a transaction factory for isolated adapter tests."""
        self._atomic_factory = atomic_factory
        self._context = None

    def __enter__(self) -> "DjangoCRMUnitOfWork":
        """Begin the CRM transaction."""
        self._context = self._atomic_factory()
        self._context.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback) -> bool | None:
        """Commit successful CRM writes or roll them back together."""
        return self._context.__exit__(exception_type, exception, traceback)
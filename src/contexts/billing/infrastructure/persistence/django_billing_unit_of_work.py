from django.db import transaction


class DjangoBillingUnitOfWork:
    """Keep Billing aggregates, idempotency rows, and Outbox writes on one connection."""

    def __init__(self, atomic_factory=transaction.atomic) -> None:
        self._atomic_factory = atomic_factory
        self._context = None

    def __enter__(self):
        self._context = self._atomic_factory()
        self._context.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        return self._context.__exit__(exception_type, exception, traceback)
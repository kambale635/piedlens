from django.db import transaction


class DjangoPaymentsUnitOfWork:
    """Keep one PaymentAttempt, provider event, event ledger and Outbox atomic (INV-TR-01/02/03)."""

    def __enter__(self):
        self._atomic = transaction.atomic()
        self._atomic.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        return self._atomic.__exit__(exception_type, exception, traceback)

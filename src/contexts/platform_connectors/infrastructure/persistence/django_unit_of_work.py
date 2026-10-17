from django.db import transaction


class DjangoPlatformConnectorsUnitOfWork:
    """Run connector aggregate, message, and Outbox writes on one DB transaction (INV-TR-02)."""

    def __enter__(self):
        """Open the atomic transaction used by this connector operation."""
        self._transaction = transaction.atomic()
        self._transaction.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        """Commit all writes together or roll them back on any failure."""
        return self._transaction.__exit__(exception_type, exception, traceback)
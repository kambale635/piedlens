from django.db import transaction


class DjangoBackupUnitOfWork:
    """Commit Backup-owned persistence and Outbox events in one PostgreSQL transaction."""

    def __enter__(self):
        """Open the Backup database transaction."""
        self._transaction = transaction.atomic()
        self._transaction.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        """Commit on success or roll back all Backup-owned writes on error."""
        return self._transaction.__exit__(exception_type, exception, traceback)
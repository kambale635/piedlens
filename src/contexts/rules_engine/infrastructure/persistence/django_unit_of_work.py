from django.db import transaction


class DjangoRulesEngineUnitOfWork:
    """Commit RuleSet/evaluation changes and their Outbox marker atomically (INV-TR-02)."""

    def __enter__(self):
        """Open the Rules Engine transaction boundary."""
        self._transaction = transaction.atomic()
        self._transaction.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        """Commit on success or roll back all context-owned writes on failure."""
        return self._transaction.__exit__(exception_type, exception, traceback)
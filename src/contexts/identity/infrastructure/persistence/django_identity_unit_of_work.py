from django.db import transaction


class DjangoIdentityUnitOfWork:
    def __init__(self, atomic_factory=transaction.atomic) -> None:
        self.atomic_factory = atomic_factory
        self.context = None

    def __enter__(self):
        self.context = self.atomic_factory()
        self.context.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        return self.context.__exit__(exception_type, exception, traceback)
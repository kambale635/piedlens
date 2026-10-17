from contexts.access_control.application.use_cases.check_permission_use_case import CheckPermissionUseCase
from contexts.access_control.infrastructure.adapters.django_permission_cache import DjangoPermissionCache
from contexts.access_control.infrastructure.persistence.django_access_control_repository import (
    DjangoAccessControlRepository,
)


class DjangoAccessControlPermissionChecker:
    def __init__(self, cache=None, repository=None) -> None:
        self.cache = cache or DjangoPermissionCache()
        self.repository = repository or DjangoAccessControlRepository()
        self.use_case = CheckPermissionUseCase(self.repository, self.cache)

    def can(self, user_id, permission, scope):
        return self.use_case.execute(user_id, permission, scope)["allowed"]
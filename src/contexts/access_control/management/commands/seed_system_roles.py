from uuid import uuid4

from django.core.management.base import BaseCommand

from contexts.access_control.domain.entities.role import Role
from contexts.access_control.infrastructure.adapters.django_permission_catalog import (
    DjangoPermissionCatalog,
)
from contexts.access_control.infrastructure.persistence.django_access_control_repository import (
    DjangoAccessControlRepository,
)
from contexts.access_control.infrastructure.adapters.system_clock import SystemAccessControlClock


class Command(BaseCommand):
    help = "Create or update the built-in Access Control roles."

    def handle(self, *args, **options):
        repository = DjangoAccessControlRepository()
        permissions = DjangoPermissionCatalog().declared_permissions()
        now = SystemAccessControlClock().now_utc()
        for name, grants in (
            ("Owner", permissions),
            ("Staff", frozenset()),
            ("PlatformAdmin", permissions),
        ):
            existing = repository.find_role_by_name(name)
            role = Role(
                existing.id if existing else uuid4(),
                name,
                grants,
                True,
                existing.created_at if existing else now,
                "system",
                "system" if existing else None,
            )
            repository.save_role(role)
        self.stdout.write(self.style.SUCCESS("System roles seeded."))
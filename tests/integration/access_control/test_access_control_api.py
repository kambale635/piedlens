import json
from types import SimpleNamespace
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase, override_settings

from contexts.access_control.infrastructure.adapters.django_permission_catalog import (
    DjangoPermissionCatalog,
)
from contexts.access_control.infrastructure.persistence.models import RoleRecord


class AllowPermissionChecker:
    def can(self, **kwargs):
        return True


class AccessControlApiTests(TestCase):
    def setUp(self):
        self.user_id = uuid4()
        self.merchant_id = uuid4()

    def _authenticate(self, request):
        return SimpleNamespace(
            id=self.user_id,
            merchant_id=self.merchant_id,
            is_authenticated=True,
        )

    def test_role_route_persists_actor_and_catalog_is_route_derived(self):
        with override_settings(
            PIEDLENS_AUTHENTICATOR=self._authenticate,
            PIEDLENS_PERMISSION_CHECKER=AllowPermissionChecker(),
        ):
            response = self.client.post(
                "/api/v1/roles",
                data=json.dumps({"name": "Support", "permissions": ["role.assign"]}),
                content_type="application/json",
                HTTP_X_MERCHANT_ID=str(self.merchant_id),
            )
        self.assertEqual(response.status_code, 201, response.content)
        role = RoleRecord.objects.get(id=response.json()["roleId"])
        self.assertEqual(role.created_by, str(self.user_id))
        self.assertIn("role.create", DjangoPermissionCatalog().declared_permissions())
        self.assertNotIn("contact.read", DjangoPermissionCatalog().declared_permissions())

    def test_seed_system_roles_is_idempotent_and_uses_declared_permissions(self):
        call_command("seed_system_roles", verbosity=0)
        call_command("seed_system_roles", verbosity=0)
        owner = RoleRecord.objects.get(name="Owner")
        self.assertTrue(owner.is_system)
        self.assertEqual(set(owner.permissions), set(DjangoPermissionCatalog().declared_permissions()))
        self.assertEqual(RoleRecord.objects.filter(is_system=True).count(), 3)
import json
from types import SimpleNamespace
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import resolve

from contexts.access_control.infrastructure.adapters.django_permission_catalog import (
    DjangoPermissionCatalog,
)
from contexts.access_control.infrastructure.adapters.django_permission_checker import (
    DjangoAccessControlPermissionChecker,
)
from contexts.access_control.infrastructure.persistence.models import (
    RoleAssignmentRecord,
    RoleRecord,
)


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
        self.assertIn("contact.read", DjangoPermissionCatalog().declared_permissions())
        self.assertIn("order.review", DjangoPermissionCatalog().declared_permissions())

    def test_context_routes_declare_catalogued_permissions_and_signed_webhooks_are_public(self):
        expected = {
            "/api/v1/contacts": "contact.read",
            "/api/v1/contacts/merge": "contact.merge",
            "/api/v1/segments": "segment.create",
            "/api/v1/segments/00000000-0000-0000-0000-000000000001/members": "contact.read",
            "/api/v1/segments/00000000-0000-0000-0000-000000000001/bulk-message": "segment.bulk_message",
            "/api/v1/dashboard/dormant-money": "order.read",
            "/api/v1/orders/00000000-0000-0000-0000-000000000001/status": "order.update_status",
            "/api/v1/orders/00000000-0000-0000-0000-000000000001/reminders": "order.remind",
            "/api/v1/detection-candidates": "order.review",
            "/api/v1/detection-candidates/00000000-0000-0000-0000-000000000001/decision": "order.review",
            "/api/v1/platform-connections": "platform.connect",
            "/api/v1/backups": "backup.read",
            "/api/v1/backups/exports/00000000-0000-0000-0000-000000000001": "backup.read",
            "/api/v1/backups/00000000-0000-0000-0000-000000000001/restore": "backup.restore",
            "/api/v1/merchants/00000000-0000-0000-0000-000000000001/data": "merchant.delete_data",
            "/api/v1/rule-sets/global": "rule_config.edit",
        }
        for route, permission in expected.items():
            with self.subTest(route=route):
                self.assertEqual(resolve(route).func.required_permission, permission)
        for route in ("/api/v1/webhooks/whatsapp", "/api/v1/webhooks/instagram"):
            with self.subTest(route=route):
                callback = resolve(route).func
                self.assertTrue(callback.public_route)
                self.assertFalse(hasattr(callback, "required_permission"))

    def test_seed_system_roles_is_idempotent_and_uses_declared_permissions(self):
        call_command("seed_system_roles", verbosity=0)
        call_command("seed_system_roles", verbosity=0)
        owner = RoleRecord.objects.get(name="Owner")
        staff = RoleRecord.objects.get(name="Staff")
        platform_admin = RoleRecord.objects.get(name="PlatformAdmin")
        catalog = set(DjangoPermissionCatalog().declared_permissions())
        self.assertTrue(owner.is_system)
        self.assertEqual(set(owner.permissions), catalog)
        self.assertEqual(set(platform_admin.permissions), catalog)
        self.assertLessEqual(set(owner.permissions) | set(staff.permissions), catalog)
        self.assertEqual(
            set(staff.permissions),
            {
                "order.read", "order.update_status", "order.remind", "order.review",
                "contact.read", "contact.merge", "segment.create", "segment.bulk_message",
                "backup.read", "backup.restore",
            },
        )
        self.assertNotIn("merchant.delete_data", staff.permissions)
        self.assertEqual(RoleRecord.objects.filter(is_system=True).count(), 3)

    def test_merchant_owner_cannot_use_global_plan_manage_permission(self):
        now = timezone.now()
        owner_role = RoleRecord.objects.create(
            id=uuid4(),
            name="Owner",
            permissions=["plan.manage"],
            is_system=True,
            created_at=now,
            created_by="system",
        )
        RoleAssignmentRecord.objects.create(
            id=uuid4(),
            user_id=self.user_id,
            role_id=owner_role.id,
            scope_type="merchant",
            scope_id=self.merchant_id,
            granted_by="system",
            granted_at=now,
        )

        with override_settings(
            PIEDLENS_AUTHENTICATOR=self._authenticate,
            PIEDLENS_PERMISSION_CHECKER=DjangoAccessControlPermissionChecker(),
        ):
            response = self.client.put(
                "/api/v1/admin/outbound-rates",
                data=json.dumps({"country": "US"}),
                content_type="application/json",
                HTTP_X_MERCHANT_ID=str(self.merchant_id),
            )

        self.assertEqual(response.status_code, 403, response.content)
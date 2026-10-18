import json
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.converters import IntConverter, PathConverter, SlugConverter, StringConverter, UUIDConverter

from contexts.access_control.infrastructure.persistence.models import (
    RoleAssignmentRecord,
    RoleRecord,
)
from contexts.crm.infrastructure.persistence.models import ContactRecord, SegmentRecord
from contexts.identity.infrastructure.adapters.django_security_services import DjangoTokenService
from contexts.identity.infrastructure.persistence.models import UserRecord


class TenantRouteIsolationTests(TestCase):
    def setUp(self):
        self.merchant_a = uuid4()
        self.merchant_b = uuid4()
        self.user = UserRecord.objects.create(
            id=uuid4(),
            phone_number="+14155550123",
            email=None,
            password_hash="unused-test-hash",
            status="active",
            created_at=timezone.now(),
        )
        self.role = RoleRecord.objects.create(
            id=uuid4(),
            name=f"Tenant A {uuid4()}",
            permissions=["contact.read", "segment.create"],
            is_system=False,
            created_at=timezone.now(),
            created_by=str(self.user.id),
        )
        RoleAssignmentRecord.objects.create(
            id=uuid4(),
            user_id=self.user.id,
            role_id=self.role.id,
            scope_type="merchant",
            scope_id=self.merchant_a,
            granted_by=str(self.user.id),
            granted_at=timezone.now(),
        )
        for merchant_id, display_name in (
            (self.merchant_a, "A private contact"),
            (self.merchant_b, "B private contact"),
        ):
            ContactRecord.objects.create(
                id=uuid4(),
                merchant_id=merchant_id,
                platform_connection_id=uuid4(),
                external_identifier=f"external-{merchant_id}",
                display_name=display_name,
                last_interaction_at=timezone.now(),
            )
        self.access_token = DjangoTokenService().issue_tokens(self.user.id)["accessToken"]

    def test_user_can_read_and_write_only_with_the_assigned_merchant_scope(self):
        headers_a = self._headers(self.merchant_a)
        headers_b = self._headers(self.merchant_b)

        read_a = self.client.get("/api/v1/contacts", **headers_a)
        read_b = self.client.get("/api/v1/contacts", **headers_b)
        write_a = self.client.post(
            "/api/v1/segments",
            data=json.dumps(
                {
                    "name": "A segment",
                    "definitionRule": {
                        "field": "order_count",
                        "operator": ">",
                        "value": 0,
                    },
                }
            ),
            content_type="application/json",
            **headers_a,
        )
        write_b = self.client.post(
            "/api/v1/segments",
            data=json.dumps(
                {
                    "name": "B segment attempt",
                    "definitionRule": {
                        "field": "order_count",
                        "operator": ">",
                        "value": 0,
                    },
                }
            ),
            content_type="application/json",
            **headers_b,
        )

        self.assertEqual(read_a.status_code, 200)
        self.assertEqual(
            [contact["displayName"] for contact in read_a.json()["contacts"]],
            ["A private contact"],
        )
        self.assertEqual(read_b.status_code, 403)
        self.assertEqual(read_b.json()["errorCode"], "FORBIDDEN")
        self.assertEqual(write_a.status_code, 201)
        self.assertEqual(write_b.status_code, 403)
        self.assertFalse(SegmentRecord.objects.filter(merchant_id=self.merchant_b).exists())

    def test_every_permission_protected_route_rejects_merchant_b_for_a_only_user(self):
        routes = self._permission_routes(get_resolver().url_patterns)
        self.assertTrue(routes)

        for route, permission in routes:
            with self.subTest(route=route, permission=permission):
                response = self.client.generic(
                    "GET",
                    route,
                    data="{}",
                    content_type="application/json",
                    **self._headers(self.merchant_b),
                )
                self.assertEqual(response.status_code, 403, response.content)

        self.assertFalse(SegmentRecord.objects.filter(merchant_id=self.merchant_b).exists())

    @classmethod
    def _permission_routes(cls, patterns, prefix=""):
        routes = []
        converter_names = {
            UUIDConverter: "uuid",
            IntConverter: "int",
            SlugConverter: "slug",
            StringConverter: "str",
            PathConverter: "path",
        }
        for pattern in patterns:
            route = f"{prefix}{pattern.pattern}"
            if isinstance(pattern, URLResolver):
                routes.extend(cls._permission_routes(pattern.url_patterns, route))
                continue
            if not isinstance(pattern, URLPattern):
                continue
            permission = getattr(pattern.callback, "required_permission", None)
            if not permission:
                continue
            for parameter, converter in pattern.pattern.converters.items():
                converter_name = converter_names[type(converter)]
                value = str(uuid4()) if isinstance(converter, UUIDConverter) else "tenant-probe"
                route = route.replace(f"<{converter_name}:{parameter}>", value)
            routes.append((f"/{route.lstrip('/')}", permission))
        return routes

    def _headers(self, merchant_id):
        return {
            "HTTP_AUTHORIZATION": f"Bearer {self.access_token}",
            "HTTP_X_MERCHANT_ID": str(merchant_id),
        }
import json
import unittest
from types import SimpleNamespace

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from middleware.audit_logging_middleware import AuditLoggingMiddleware
from middleware.authentication_middleware import AuthenticationMiddleware
from middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from middleware.permission_middleware import PermissionMiddleware
from middleware.rate_limit_middleware import RateLimitMiddleware
from middleware.request_id_middleware import RequestIdMiddleware
from middleware.route_policy import allow_anonymous, public_route, requires_permission
from middleware.tenant_isolation_middleware import TenantIsolationMiddleware
from shared_kernel.application_exceptions import ValidationException


class MiddlewareChainTests(unittest.TestCase):
    def setUp(self):
        audit_settings = override_settings(PIEDLENS_AUDIT_SINK=None)
        audit_settings.enable()
        self.addCleanup(audit_settings.disable)
        self.factory = RequestFactory()
        self.request = self.factory.get("/api/resource")
        self.request.correlation_id = "correlation-1"
        self.request.user = SimpleNamespace(id="user-1", is_authenticated=True, merchant_id="merchant-1")
        self.request.merchant_id = "merchant-1"

    def test_request_id_is_generated_and_returned(self):
        middleware = RequestIdMiddleware(lambda request: HttpResponse("ok"))
        response = middleware(self.request)
        self.assertEqual(response["X-Correlation-ID"], self.request.correlation_id)

    def test_exception_handler_maps_validation_and_hides_unexpected_detail(self):
        validation = ExceptionHandlingMiddleware(lambda request: (_ for _ in ()).throw(ValidationException("bad")))
        response = validation(self.request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["errorCode"], "VALIDATION_ERROR")

        unexpected = ExceptionHandlingMiddleware(lambda request: (_ for _ in ()).throw(RuntimeError("secret")))
        response = unexpected(self.request)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.content.decode())

    def test_authentication_requires_principal_except_explicit_public_route(self):
        middleware = AuthenticationMiddleware(lambda request: None)
        view = lambda request: None
        self.request.user.is_authenticated = False
        response = middleware.process_view(self.request, view, (), {})
        self.assertEqual(response.status_code, 401)

        public_view = allow_anonymous(lambda request: None)
        self.assertIsNone(middleware.process_view(self.request, public_view, (), {}))

        authenticated_view = public_route(lambda request: None, authentication_required=True)
        response = middleware.process_view(self.request, authenticated_view, (), {})
        self.assertEqual(response.status_code, 401)

    def test_tenant_scope_comes_from_authenticated_principal(self):
        middleware = TenantIsolationMiddleware(lambda request: None)
        view = lambda request: None
        self.assertIsNone(middleware.process_view(self.request, view, (), {}))
        self.assertEqual(self.request.merchant_id, "merchant-1")
        self.request.user.merchant_id = None
        response = middleware.process_view(self.request, view, (), {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content)["errorCode"], "TENANT_REQUIRED")

    def test_tenant_route_parameter_cannot_override_authenticated_scope(self):
        middleware = TenantIsolationMiddleware(lambda request: None)
        view = lambda request, merchant_id: None

        response = middleware.process_view(
            self.request, view, (), {"merchant_id": "different-merchant"}
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content)["errorCode"], "TENANT_REQUIRED")

    def test_permission_is_delegated_and_fails_closed(self):
        class Checker:
            def __init__(self, allowed):
                self.allowed = allowed
                self.calls = []

            def can(self, **kwargs):
                self.calls.append(kwargs)
                return self.allowed

        view = requires_permission("contact.read")(lambda request: None)
        checker = Checker(True)
        middleware = PermissionMiddleware(lambda request: None)
        with override_settings(PIEDLENS_PERMISSION_CHECKER=checker):
            self.assertIsNone(middleware.process_view(self.request, view, (), {}))
        self.assertEqual(checker.calls[0]["permission"], "contact.read")

        with override_settings(PIEDLENS_PERMISSION_CHECKER=None):
            response = middleware.process_view(self.request, view, (), {})
        self.assertEqual(response.status_code, 403)

    def test_rule_scope_requires_global_assignment_for_global_and_country_rules(self):
        class ScopeChecker:
            def __init__(self):
                self.scopes = []

            def can(self, **kwargs):
                self.scopes.append(kwargs["scope"])
                return kwargs["scope"] != "global"

        view = requires_permission("rule_config.edit", global_scope_param="scope")(
            lambda request: None
        )
        self.request.resolver_match = SimpleNamespace(kwargs={"scope": "country:CI"})
        checker = ScopeChecker()
        middleware = PermissionMiddleware(lambda request: None)
        with override_settings(PIEDLENS_PERMISSION_CHECKER=checker):
            response = middleware.process_view(self.request, view, (), {})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(checker.scopes, ["merchant-1", "global"])

    def test_unmarked_route_is_denied_and_public_route_is_explicit(self):
        middleware = PermissionMiddleware(lambda request: None)
        unmarked_view = lambda request: None
        response = middleware.process_view(self.request, unmarked_view, (), {})
        self.assertEqual(response.status_code, 403)

        public_view = public_route(lambda request: None)
        self.assertIsNone(middleware.process_view(self.request, public_view, (), {}))

    def test_rate_limit_uses_injected_limiter(self):
        class Limiter:
            def allow(self, **kwargs):
                return False

        middleware = RateLimitMiddleware(lambda request: None)
        view = requires_permission("contact.read")(lambda request: None)
        with override_settings(PIEDLENS_RATE_LIMITER=Limiter()):
            response = middleware.process_view(self.request, view, (), {})
        self.assertEqual(response.status_code, 429)

    def test_audit_records_metadata_and_response_outcome(self):
        events = []
        self.request.verified_permission = "contact.read"
        middleware = AuditLoggingMiddleware(lambda request: HttpResponse("message body"))
        with override_settings(PIEDLENS_AUDIT_SINK=events.append):
            response = middleware(self.request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(events[0]["permission"], "contact.read")
        self.assertNotIn("message body", str(events[0]))


if __name__ == "__main__":
    unittest.main()

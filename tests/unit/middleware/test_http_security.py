import json
import unittest

from django.core.exceptions import RequestDataTooBig
from django.http import HttpResponse
from django.middleware.clickjacking import XFrameOptionsMiddleware
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, override_settings

from config.security_settings import environment_security_settings
from middleware.cors_middleware import CorsMiddleware
from middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from middleware.request_size_limit_middleware import RequestSizeLimitMiddleware


class HttpSecurityTests(unittest.TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_production_forces_secure_cookies_redirect_and_hsts(self):
        options = environment_security_settings({"DJANGO_ENV": "production"})

        self.assertTrue(options["SESSION_COOKIE_SECURE"])
        self.assertTrue(options["CSRF_COOKIE_SECURE"])
        self.assertTrue(options["SECURE_SSL_REDIRECT"])
        self.assertGreater(options["SECURE_HSTS_SECONDS"], 0)

    def test_security_middleware_emits_hsts_and_browser_headers(self):
        request = self.factory.get("/", secure=True)
        with override_settings(
            SECURE_HSTS_SECONDS=3600,
            SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
            SECURE_CONTENT_TYPE_NOSNIFF=True,
            SECURE_REFERRER_POLICY="strict-origin-when-cross-origin",
            X_FRAME_OPTIONS="DENY",
        ):
            middleware = SecurityMiddleware(lambda current: HttpResponse("ok"))
            security_response = middleware(request)
            response = XFrameOptionsMiddleware(lambda current: security_response)(request)

        self.assertIn("max-age=3600", response["Strict-Transport-Security"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")

    @override_settings(
        CORS_ALLOWED_ORIGINS=("https://console.example",),
        CORS_ALLOWED_METHODS=("GET", "POST", "OPTIONS"),
        CORS_ALLOWED_HEADERS=("authorization", "content-type"),
    )
    def test_cors_allows_only_exact_origin_methods_and_headers(self):
        middleware = CorsMiddleware(lambda request: HttpResponse("ok"))
        allowed = self.factory.options(
            "/api/v1/contacts",
            HTTP_ORIGIN="https://console.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization, content-type",
        )
        denied = self.factory.options(
            "/api/v1/contacts",
            HTTP_ORIGIN="https://attacker.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )

        allowed_response = middleware(allowed)
        denied_response = middleware(denied)

        self.assertEqual(allowed_response.status_code, 204)
        self.assertEqual(allowed_response["Access-Control-Allow-Origin"], "https://console.example")
        self.assertNotIn("Access-Control-Allow-Credentials", allowed_response)
        self.assertEqual(denied_response.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", denied_response)

    @override_settings(DJANGO_MAX_REQUEST_BODY_BYTES=4)
    def test_oversized_request_is_rejected_before_view_execution(self):
        called = []
        middleware = RequestSizeLimitMiddleware(lambda request: called.append(True) or HttpResponse())
        request = self.factory.post(
            "/api/v1/auth/login", data="12345", content_type="application/json"
        )
        request.correlation_id = "request-1"

        response = middleware(request)

        self.assertEqual(response.status_code, 413)
        self.assertEqual(json.loads(response.content)["errorCode"], "REQUEST_TOO_LARGE")
        self.assertEqual(called, [])

    def test_django_request_size_exception_maps_to_413(self):
        request = self.factory.post("/")
        response = ExceptionHandlingMiddleware._exception_response(
            request, RequestDataTooBig("oversized")
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(json.loads(response.content)["errorCode"], "REQUEST_TOO_LARGE")

    def test_unexpected_exception_logs_neither_message_nor_payment_content(self):
        message_secret = "private-message-log-sentinel"
        payment_secret = "private-payment-log-sentinel"
        request = self.factory.get("/")
        request.correlation_id = "error-correlation-1"
        middleware = ExceptionHandlingMiddleware(
            lambda current: (_ for _ in ()).throw(
                RuntimeError(f"{message_secret} {payment_secret}")
            )
        )

        with self.assertLogs("middleware.exception_handling_middleware", level="ERROR") as captured:
            response = middleware(request)

        self.assertEqual(response.status_code, 500)
        log_content = "\n".join(captured.output)
        self.assertIn("error-correlation-1", log_content)
        self.assertNotIn(message_secret, log_content)
        self.assertNotIn(payment_secret, log_content)


if __name__ == "__main__":
    unittest.main()
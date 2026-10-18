import json
from types import SimpleNamespace

from django.http import HttpResponse
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, TestCase

from middleware.audit_logging_middleware import AuditLoggingMiddleware
from piedlens_platform.event_bus.models import AuditLogRecord


class AuditLogSecurityTests(TestCase):
    def test_sensitive_request_body_is_not_logged_or_persisted(self):
        message_secret = "private-customer-message-unique"
        payment_secret = "payment-reference-unique"
        request = RequestFactory().post(
            "/api/v1/webhooks/whatsapp",
            data=json.dumps({"text": message_secret, "paymentReference": payment_secret}),
            content_type="application/json",
        )
        request.correlation_id = "audit-correlation-1"
        request.user = SimpleNamespace(id="user-a", is_authenticated=True)
        request.merchant_id = "merchant-a"
        request.verified_permission = "platform.connect"
        middleware = AuditLoggingMiddleware(lambda current: HttpResponse("ok"))

        with self.assertLogs("piedlens.audit", level="INFO") as captured:
            response = middleware(request)

        log_content = "\n".join(captured.output) + repr(captured.records[0].__dict__)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(message_secret, log_content)
        self.assertNotIn(payment_secret, log_content)
        audit_record = AuditLogRecord.objects.get(correlation_id="audit-correlation-1")
        self.assertEqual(audit_record.route, "/api/v1/webhooks/whatsapp")
        self.assertNotIn(message_secret, repr(audit_record.__dict__))
        self.assertNotIn(payment_secret, repr(audit_record.__dict__))

    def test_audit_records_reject_update_and_delete_operations(self):
        record = AuditLogRecord.objects.create(
            correlation_id="audit-immutable-1",
            outcome="allowed",
            route="/api/v1/contacts",
        )

        record.route = "/api/v1/changed"
        with self.assertRaisesRegex(ValueError, "append-only"):
            record.save()
        with self.assertRaisesRegex(ValueError, "append-only"):
            AuditLogRecord.objects.filter(id=record.id).update(route="/api/v1/changed")
        with self.assertRaisesRegex(ValueError, "append-only"):
            record.delete()
        with self.assertRaisesRegex(ValueError, "append-only"):
            AuditLogRecord.objects.filter(id=record.id).delete()

    def test_postgresql_trigger_rejects_raw_update_and_delete(self):
        if connection.vendor != "postgresql":
            self.skipTest("Database-level append-only trigger is PostgreSQL-specific.")
        record = AuditLogRecord.objects.create(
            correlation_id="audit-trigger-1",
            outcome="allowed",
            route="/api/v1/contacts",
        )

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE event_bus_audit_log SET route = %s WHERE id = %s",
                        ["/api/v1/changed", str(record.id)],
                    )
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM event_bus_audit_log WHERE id = %s", [str(record.id)]
                    )
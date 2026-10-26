import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase, override_settings

from contexts.billing.infrastructure.persistence.models import PlanDefinitionRecord, PlanEntitlementRecord
from contexts.identity.infrastructure.persistence.models import MerchantRecord
from contexts.platform_connectors.infrastructure.persistence.models import (
    ConversationImportRecord,
    ImportFormatRecord,
    MessageRecord,
    OutboxEventRecord,
)


class AllowPermissionChecker:
    def can(self, **kwargs):
        return True


class ManualConversationImportIntegrationTests(TestCase):
    def setUp(self):
        call_command("seed_billing_plans", verbosity=0)
        call_command("seed_import_formats", verbosity=0)
        plan = PlanDefinitionRecord.objects.get(code="starter")
        PlanEntitlementRecord.objects.update_or_create(
            plan=plan, key="manual_import", defaults={"value": True}
        )
        self.merchant_id = uuid4()
        MerchantRecord.objects.create(
            id=self.merchant_id,
            name="Import merchant",
            country="CD",
            preferred_language="fr",
            currency="USD",
            subscription_plan="starter",
            created_at=datetime.now(timezone.utc),
        )

    def authenticate(self, request):
        return SimpleNamespace(
            id=uuid4(), merchant_id=self.merchant_id, is_authenticated=True
        )

    @override_settings(
        PIEDLENS_AUTHENTICATOR=lambda request: None,
        PIEDLENS_PERMISSION_CHECKER=AllowPermissionChecker(),
        DJANGO_MAX_REQUEST_BODY_BYTES=2048,
    )
    def test_consent_submission_is_queued_and_worker_emits_one_encrypted_message(self):
        with override_settings(PIEDLENS_AUTHENTICATOR=self.authenticate):
            response = self.client.post(
                "/api/v1/imports",
                data=json.dumps({
                    "formatCode": "json_messages_v1",
                    "content": json.dumps({"messages": [
                        {
                            "id": "manual-1",
                            "sender": "seller-customer",
                            "text": "Bonjour",
                            "timestamp": "2026-10-25T10:00:00Z",
                        },
                        {
                            "id": "manual-outside-range",
                            "sender": "seller-customer",
                            "text": "Hors plage",
                            "timestamp": "2026-10-26T10:00:00Z",
                        },
                    ]}),
                    "consentId": str(uuid4()),
                    "consentGiven": True,
                    "selectedRange": {
                        "from": "2026-10-25T00:00:00Z",
                        "to": "2026-10-25T23:59:59Z",
                    },
                }),
                content_type="application/json",
                HTTP_X_MERCHANT_ID=str(self.merchant_id),
            )
        self.assertEqual(response.status_code, 202, response.content)
        import_id = response.json()["importId"]
        task = ConversationImportRecord.objects.get(id=import_id)
        self.assertEqual(task.status, "queued")
        self.assertNotIn("Bonjour", task.encrypted_content)

        call_command("process_conversation_imports", verbosity=0)
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.accepted_count, 1)
        self.assertEqual(MessageRecord.objects.filter(merchant_id=self.merchant_id).count(), 1)
        message = MessageRecord.objects.get(merchant_id=self.merchant_id)
        self.assertNotIn("Bonjour", message.text_content)
        self.assertEqual(
            OutboxEventRecord.objects.filter(event_type="MessageReceived").count(),
            1,
        )

        with override_settings(PIEDLENS_AUTHENTICATOR=self.authenticate):
            status = self.client.get(
                f"/api/v1/imports/{import_id}",
                HTTP_X_MERCHANT_ID=str(self.merchant_id),
            )
        self.assertEqual(status.status_code, 200, status.content)
        self.assertEqual(status.json()["status"], "completed")
        self.assertNotIn("Bonjour", status.content.decode())

    @override_settings(
        PIEDLENS_AUTHENTICATOR=lambda request: None,
        PIEDLENS_PERMISSION_CHECKER=AllowPermissionChecker(),
    )
    def test_missing_consent_is_rejected(self):
        with override_settings(PIEDLENS_AUTHENTICATOR=self.authenticate):
            response = self.client.post(
                "/api/v1/imports",
                data=json.dumps({
                    "formatCode": "json_messages_v1",
                    "content": "{}",
                    "consentId": str(uuid4()),
                    "consentGiven": False,
                    "selectedRange": {"from": "2026-10-25"},
                }),
                content_type="application/json",
                HTTP_X_MERCHANT_ID=str(self.merchant_id),
            )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(ConversationImportRecord.objects.count(), 0)

    def test_new_format_is_enabled_by_configuration_data(self):
        ImportFormatRecord.objects.create(
            code="fake_channel_export_v1",
            version=1,
            active=True,
            parser_key="configured_lines_v1",
            language="en",
            config={
                "line_pattern": r"^(?P<timestamp>.+?) \| (?P<sender>[^|]+) \| (?P<text>.*)$",
                "timestamp_formats": ["%Y-%m-%d %H:%M"],
            },
        )
        from contexts.platform_connectors.application.services.import_format_parser import (
            ImportFormatParser,
        )
        from contexts.platform_connectors.infrastructure.persistence.django_import_format_reader import (
            DjangoImportFormatReader,
        )

        format_config = DjangoImportFormatReader().find_active("fake_channel_export_v1")
        parsed = ImportFormatParser().parse(
            "2026-10-25 10:15 | customer | hello",
            format_config["parser_key"],
            format_config["config"],
        )
        self.assertEqual(parsed[0]["external_sender_id"], "customer")

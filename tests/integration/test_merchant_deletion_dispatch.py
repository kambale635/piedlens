from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from piedlens_platform.event_bus.handlers import handle_merchant_data_deleted


class MerchantDeletionDispatchTests(SimpleTestCase):
    def test_dispatches_only_backup_deletion_events_to_selected_context(self):
        envelope = {
            "eventType": "MerchantDataDeleted",
            "producedBy": "backup",
            "eventId": "event-id",
            "payload": {"merchant_id": "merchant-id"},
        }
        cases = {
            "identity": "contexts.identity.infrastructure.messaging.merchant_data_deletion_handler",
            "access-control": "contexts.access_control.infrastructure.messaging.merchant_data_deletion_handler",
            "platform-connectors": "contexts.platform_connectors.infrastructure.messaging.merchant_data_deletion_handler",
            "rules-engine": "contexts.rules_engine.infrastructure.messaging.merchant_data_deletion_handler",
            "order-detection": "contexts.order_detection.infrastructure.messaging.merchant_data_deletion_handler",
            "crm": "contexts.crm.infrastructure.messaging.merchant_data_deletion_handler",
        }

        for context, module_path in cases.items():
            with self.subTest(context=context), override_settings(CONSUMER_CONTEXT=context):
                with patch(f"{module_path}.handle_merchant_data_deleted") as handler:
                    handle_merchant_data_deleted(envelope)
                handler.assert_called_once_with(envelope)

    def test_ignores_non_deletion_events(self):
        with override_settings(CONSUMER_CONTEXT="identity"):
            handle_merchant_data_deleted(
                {"eventType": "MerchantRegistered", "producedBy": "identity"}
            )

    def test_rejects_unconfigured_consumer_context(self):
        with override_settings(CONSUMER_CONTEXT="unknown"):
            with self.assertRaisesRegex(ValueError, "consumer context is not configured"):
                handle_merchant_data_deleted(
                    {"eventType": "MerchantDataDeleted", "producedBy": "backup"}
                )
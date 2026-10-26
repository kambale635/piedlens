import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.platform_connectors.application.services.import_format_parser import ImportFormatParser
from contexts.platform_connectors.application.use_cases.submit_conversation_import_use_case import SubmitConversationImportUseCase
from shared_kernel.application_exceptions import ValidationException


class ImportFormatParserTests(unittest.TestCase):
    def test_configured_json_formats_normalize_messages_without_channel_names(self):
        messages = ImportFormatParser().parse(
            '{"messages":[{"id":"m-1","sender":"customer-1","text":"hello","timestamp":"2026-10-25T10:00:00Z"}]}',
            "json_messages_v1",
            {},
        )
        self.assertEqual(messages[0]["external_message_id"], "m-1")
        self.assertEqual(messages[0]["received_at"], datetime(2026, 10, 25, 10, tzinfo=timezone.utc))

    def test_configured_line_format_uses_configured_date_patterns(self):
        messages = ImportFormatParser().parse(
            "25/10/2026, 10:30 - Client: bonjour",
            "configured_lines_v1",
            {
                "line_pattern": r"^(?P<timestamp>.+?) - (?P<sender>[^:]+): (?P<text>.*)$",
                "timestamp_formats": ["%d/%m/%Y, %H:%M"],
            },
        )
        self.assertEqual(messages[0]["external_sender_id"], "Client")
        self.assertEqual(messages[0]["received_at"].hour, 10)

    def test_unknown_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown or inactive"):
            ImportFormatParser().parse("data", "unknown", {})


class SubmitConversationImportTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.imports = InMemoryImports()
        self.use_case = SubmitConversationImportUseCase(
            formats=InMemoryFormats(),
            imports=self.imports,
            entitlements=InMemoryEntitlements(),
            cipher=IdentityCipher(),
            clock=FixedClock(),
            max_bytes=1024,
        )

    def execute(self, **overrides):
        arguments = {
            "merchant_id": self.merchant_id,
            "format_code": "json_messages_v1",
            "content": '{"messages":[]}',
            "consent_id": uuid4(),
            "consent": True,
            "selected_range": {"from": "2026-10-01", "to": "2026-10-02"},
        }
        arguments.update(overrides)
        return self.use_case.execute(**arguments)

    def test_submission_is_encrypted_queued_and_idempotent(self):
        first = self.execute()
        replay = self.execute()
        self.assertEqual(first.import_id, replay.import_id)
        self.assertFalse(first.duplicate)
        self.assertTrue(replay.duplicate)
        self.assertEqual(self.imports.values[0]["encrypted_content"], "encrypted")
        self.assertIsNotNone(self.imports.values[0]["consent_id"])

    def test_consent_and_plan_entitlement_are_required(self):
        with self.assertRaises(ValidationException):
            self.execute(consent=False)
        self.use_case._entitlements.enabled = False
        with self.assertRaises(ValidationException):
            self.execute()


class InMemoryFormats:
    def find_active(self, code):
        return {
            "version": 1,
            "parser_key": "json_messages_v1",
        } if code == "json_messages_v1" else None


class InMemoryEntitlements:
    enabled = True

    def entitlements_for(self, merchant_id):
        return {"manual_import": self.enabled}


class IdentityCipher:
    def encrypt(self, content):
        return "encrypted"


class FixedClock:
    def now_utc(self):
        return datetime(2026, 10, 25, tzinfo=timezone.utc)


class InMemoryImports:
    def __init__(self):
        self.values = []

    def create_if_new(self, values):
        for existing in self.values:
            if existing["merchant_id"] == values["merchant_id"] and existing["content_hash"] == values["content_hash"]:
                return existing["id"], False
        record = {**values, "id": uuid4()}
        self.values.append(record)
        return record["id"], True


if __name__ == "__main__":
    unittest.main()

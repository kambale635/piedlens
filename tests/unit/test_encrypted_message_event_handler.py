import base64
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings

from contexts.platform_connectors.infrastructure.adapters.django_message_content_cipher import (
    DjangoMessageContentCipher,
)
from piedlens_platform.event_bus.handlers import handle_message_received


class EncryptedMessageEventHandlerTests(SimpleTestCase):
    @override_settings(
        PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION="v1",
        PLATFORM_MESSAGE_ENCRYPTION_KEYS={
            "v1": base64.urlsafe_b64encode(b"h" * 32).decode("ascii")
        },
        CONSUMER_CONTEXT="rules-engine",
    )
    def test_rules_engine_receives_plaintext_only_after_consumer_decryption(self):
        plaintext = "customer message content"
        ciphertext = DjangoMessageContentCipher().encrypt(plaintext)
        execute = patch("piedlens_platform.event_bus.handlers.ApplicationContainer.evaluate_message")
        with execute as build_use_case:
            use_case = build_use_case.return_value
            handle_message_received(
                {
                    "eventId": str(uuid4()),
                    "eventType": "MessageReceived",
                    "producedBy": "platform-connectors",
                    "payload": {
                        "merchant_id": str(uuid4()),
                        "platform_connection_id": str(uuid4()),
                        "message_id": str(uuid4()),
                        "external_sender_id": "sender-1",
                        "display_name": "Customer",
                        "received_at": datetime.now(timezone.utc).isoformat(),
                        "text_content": ciphertext,
                    },
                }
            )

        self.assertEqual(use_case.execute.call_args.kwargs["text_content"], plaintext)
        self.assertNotEqual(ciphertext, plaintext)

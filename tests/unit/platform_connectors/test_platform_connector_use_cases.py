import json
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contexts.platform_connectors.application.exceptions import (
    InvalidWebhookSignatureException,
    PlanConnectionLimitReachedException,
)
from contexts.platform_connectors.application.use_cases.connect_platform_use_case import (
    ConnectPlatformUseCase,
)
from contexts.platform_connectors.application.use_cases.handle_incoming_webhook_use_case import (
    HandleIncomingWebhookUseCase,
)
from contexts.platform_connectors.application.use_cases.refresh_tokens_use_case import (
    RefreshTokensUseCase,
)
from contexts.platform_connectors.application.use_cases.sync_active_connections_job import (
    SyncActiveConnectionsJob,
)
from contexts.platform_connectors.application.use_cases.sync_messages_use_case import (
    SyncMessagesResult,
)
from contexts.platform_connectors.domain.entities.message import Message
from contexts.platform_connectors.domain.entities.platform_connection import PlatformConnection
from contexts.platform_connectors.domain.value_objects.connection_status import ConnectionStatus
from contexts.platform_connectors.domain.value_objects.encrypted_token import EncryptedToken
from contexts.platform_connectors.domain.value_objects.platform_type import PlatformType


class FakeUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class FakeClock:
    def now_utc(self):
        return datetime(2026, 10, 17, tzinfo=timezone.utc)


class FakeConnections:
    def __init__(self, connections=()):
        self.items = {connection.id: connection for connection in connections}
        self.saved = []

    def find_by_id(self, connection_id):
        return self.items.get(connection_id)

    def find_active_by_merchant(self, merchant_id):
        return [item for item in self.items.values() if item.merchant_id == merchant_id]

    def save(self, connection):
        self.items[connection.id] = connection
        self.saved.append(connection)


class FakeMessageRepository:
    def __init__(self):
        self.external_ids = set()

    def save_if_new(self, message):
        key = (message.platform_connection_id, message.external_message_id)
        if key in self.external_ids:
            return False
        self.external_ids.add(key)
        return True


class FakeOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class FakeCipher:
    def encrypt(self, plaintext):
        return EncryptedToken(f"encrypted:{plaintext}")


class FakeGateway:
    def exchange_oauth_code(self, platform_type, oauth_code, external_account_id):
        return "secret-token", external_account_id or "external-1"


class FakeVerifier:
    def __init__(self, valid):
        self.valid = valid

    def verify(self, platform_type, raw_body, signature):
        return self.valid


class FakeMapper:
    def __init__(self, messages):
        self.messages = messages
        self.calls = 0

    def map_messages(self, connection, payload):
        self.calls += 1
        return self.messages


class PlatformConnectorUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.connection = PlatformConnection(
            id=uuid4(),
            merchant_id=self.merchant_id,
            platform_type=PlatformType.WHATSAPP,
            external_account_id="external-1",
            encrypted_access_token=EncryptedToken("opaque-ciphertext"),
            status=ConnectionStatus.ACTIVE,
            consent_given_at=None,
        )

    def test_connect_rejects_plan_capacity_before_oauth_exchange(self):
        gateway = FakeGateway()
        use_case = ConnectPlatformUseCase(
            connections=FakeConnections(),
            gateway=gateway,
            cipher=FakeCipher(),
            usage_reader=type("Usage", (), {"count_active_connections": lambda *_: 1})(),
            plan_reader=type("Plan", (), {"active_connection_limit": lambda *_: 1})(),
            unit_of_work=FakeUnitOfWork(),
            outbox=FakeOutbox(),
            clock=FakeClock(),
        )

        with self.assertRaises(PlanConnectionLimitReachedException):
            use_case.execute(self.merchant_id, "whatsapp", "oauth-code")

    def test_connect_encrypts_token_and_persists_outbox_event(self):
        connections = FakeConnections()
        outbox = FakeOutbox()
        use_case = ConnectPlatformUseCase(
            connections=connections,
            gateway=FakeGateway(),
            cipher=FakeCipher(),
            usage_reader=type("Usage", (), {"count_active_connections": lambda *_: 0})(),
            plan_reader=type("Plan", (), {"active_connection_limit": lambda *_: 1})(),
            unit_of_work=FakeUnitOfWork(),
            outbox=outbox,
            clock=FakeClock(),
        )

        result = use_case.execute(self.merchant_id, "whatsapp", "oauth-code", consent_given=True)

        connection = connections.find_by_id(result["platform_connection_id"])
        self.assertEqual(connection.encrypted_access_token.value, "encrypted:secret-token")
        self.assertEqual(connection.consent_given_at, FakeClock().now_utc())
        self.assertEqual(len(outbox.events), 1)

    def test_invalid_signature_is_rejected_before_payload_mapping(self):
        mapper = FakeMapper([])
        use_case = HandleIncomingWebhookUseCase(
            connections=FakeConnections([self.connection]),
            messages=FakeMessageRepository(),
            verifier=FakeVerifier(False),
            mapper=mapper,
            unit_of_work=FakeUnitOfWork(),
            outbox=FakeOutbox(),
        )

        with self.assertRaises(InvalidWebhookSignatureException):
            use_case.execute("whatsapp", b"not-json", "bad-signature")
        self.assertEqual(mapper.calls, 0)

    def test_duplicate_webhook_is_idempotent_for_message_and_outbox(self):
        message = Message(
            id=uuid4(),
            platform_connection_id=self.connection.id,
            merchant_id=self.merchant_id,
            external_message_id="provider-message-1",
            external_sender_id="sender-1",
            display_name="Customer",
            text_content="paid",
            received_at=FakeClock().now_utc(),
        )
        repository = FakeMessageRepository()
        outbox = FakeOutbox()
        use_case = HandleIncomingWebhookUseCase(
            connections=FakeConnections([self.connection]),
            messages=repository,
            verifier=FakeVerifier(True),
            mapper=FakeMapper([message]),
            unit_of_work=FakeUnitOfWork(),
            outbox=outbox,
        )
        body = json.dumps({"platformConnectionId": str(self.connection.id)}).encode()

        self.assertEqual(use_case.execute("whatsapp", body, "signature")["accepted_count"], 1)
        self.assertEqual(use_case.execute("whatsapp", body, "signature")["accepted_count"], 0)
        self.assertEqual(len(outbox.events), 1)

    def test_sync_job_continues_after_a_connection_failure(self):
        second = PlatformConnection(
            id=uuid4(),
            merchant_id=self.merchant_id,
            platform_type=PlatformType.INSTAGRAM,
            external_account_id="external-2",
            encrypted_access_token=EncryptedToken("opaque-2"),
            status=ConnectionStatus.ACTIVE,
            consent_given_at=None,
        )

        class SyncUseCase:
            def execute(self, connection_id, since):
                if connection_id == self_connection.id:
                    raise RuntimeError("provider failed")
                return SyncMessagesResult(1, FakeClock().now_utc(), "succeeded")

        self_connection = self.connection
        job = SyncActiveConnectionsJob(
            FakeConnections([self.connection, second]),
            SyncUseCase(),
        )

        result = job.execute(self.merchant_id, FakeClock().now_utc())

        self.assertEqual(len(result.results), 2)
        self.assertEqual(result.results[0][1].status, "failed")
        self.assertEqual(result.results[1][1].status, "succeeded")

    def test_refresh_token_encrypts_new_credential(self):
        class RefreshingGateway:
            def refresh_access_token(self, connection):
                return "replacement-secret"

        connections = FakeConnections([self.connection])
        use_case = RefreshTokensUseCase(
            connections,
            RefreshingGateway(),
            FakeCipher(),
            FakeUnitOfWork(),
            FakeOutbox(),
            FakeClock(),
        )

        result = use_case.execute(self.connection.id)

        self.assertEqual(result["connection_status"], "active")
        self.assertEqual(self.connection.encrypted_access_token.value, "encrypted:replacement-secret")

    def test_failed_refresh_marks_only_that_connection_expired_and_emits_event(self):
        class FailingGateway:
            def refresh_access_token(self, connection):
                raise RuntimeError("provider unavailable")

        outbox = FakeOutbox()
        use_case = RefreshTokensUseCase(
            FakeConnections([self.connection]),
            FailingGateway(),
            FakeCipher(),
            FakeUnitOfWork(),
            outbox,
            FakeClock(),
        )

        result = use_case.execute(self.connection.id)

        self.assertEqual(result["connection_status"], "expired")
        self.assertIs(self.connection.status, ConnectionStatus.EXPIRED)
        self.assertEqual(len(outbox.events), 1)


if __name__ == "__main__":
    unittest.main()
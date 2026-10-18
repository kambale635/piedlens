import hashlib
import hmac
import json
import traceback
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import redis
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone as django_timezone

from contexts.access_control.infrastructure.persistence.models import (
    RoleAssignmentRecord,
    RoleRecord,
)
from contexts.crm.infrastructure.persistence.models import ContactRecord
from contexts.identity.infrastructure.persistence.models import MerchantRecord, UserRecord
from contexts.order_detection.infrastructure.persistence.models import OrderRecord
from contexts.platform_connectors.infrastructure.persistence.models import (
    OutboxEventRecord as PlatformOutboxRecord,
    PlatformConnectionRecord,
)
from contexts.rules_engine.infrastructure.persistence.models import (
    OutboxEventRecord as RulesOutboxRecord,
    RuleSetRecord,
)
from piedlens_platform.event_bus.outbox_relay_worker import OutboxRelayWorker
from piedlens_platform.event_bus.redis_stream_publisher import RedisStreamEventPublisher
from piedlens_platform.event_bus.stream_consumer_worker import RedisStreamConsumerWorker


class MessageToDormantOrderE2ETests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
        try:
            self.redis.ping()
        except redis.RedisError as error:
            self.fail(f"Redis required for E2E message pipeline: {error}")
        self.platform_stream = f"test:e2e:platform:{uuid4()}"
        self.rules_stream = f"test:e2e:rules:{uuid4()}"
        self._groups = []
        self.merchant_id = uuid4()
        self.user_id = uuid4()
        now = django_timezone.now()
        self.user = UserRecord.objects.create(
            id=self.user_id,
            phone_number=f"+1415{uuid4().int % 10**7:07d}",
            email=None,
            password_hash="unused-e2e-hash",
            status="active",
            created_at=now,
        )
        MerchantRecord.objects.create(
            id=self.merchant_id,
            name="E2E merchant",
            country="CI",
            preferred_language="fr",
            currency="XOF",
            subscription_plan="starter",
            created_at=now,
        )
        role = RoleRecord.objects.create(
            id=uuid4(),
            name=f"E2E Owner {uuid4()}",
            permissions=["platform.connect", "order.read"],
            is_system=False,
            created_at=now,
            created_by=str(self.user_id),
        )
        RoleAssignmentRecord.objects.create(
            id=uuid4(),
            user_id=self.user_id,
            role_id=role.id,
            scope_type="merchant",
            scope_id=self.merchant_id,
            granted_by=str(self.user_id),
            granted_at=now,
        )
        self.auth_token = self._issue_access_token()
        self.headers = {
            "HTTP_AUTHORIZATION": f"Bearer {self.auth_token}",
            "HTTP_X_MERCHANT_ID": str(self.merchant_id),
        }
        RuleSetRecord.objects.create(
            id=uuid4(),
            scope=f"merchant:{self.merchant_id}",
            version=1,
            rules=[
                {
                    "rule_id": str(uuid4()),
                    "rule_type": "KeywordMatch",
                    "language": "fr",
                    "pattern": ["prends"],
                    "weight": 50,
                    "is_active": True,
                    "currency": None,
                    "config": {"intent": "purchase"},
                },
                {
                    "rule_id": str(uuid4()),
                    "rule_type": "AmountPattern",
                    "language": "fr",
                    "pattern": {
                        "regex": r"(?P<amount>\d{1,3}(?: ?\d{3})*)\s*F",
                        "groupSeparator": " ",
                        "decimalSeparator": ",",
                    },
                    "weight": 50,
                    "is_active": True,
                    "currency": "XOF",
                    "config": {},
                },
            ],
        )

    def tearDown(self):
        for stream_name, group_name in self._groups:
            try:
                self.redis.xgroup_destroy(stream_name, group_name)
            except redis.RedisError:
                pass
        self.redis.delete(self.platform_stream, self.rules_stream)

    @override_settings(
        PLATFORM_WEBHOOK_SECRETS={"whatsapp": "e2e-webhook-secret"},
        PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=300,
    )
    def test_signed_webhook_creates_scoped_contact_and_pending_order(self):
        connected = self.client.post(
            "/api/v1/platform-connections",
            data=json.dumps(
                {
                    "platformType": "whatsapp",
                    "oauthCode": "mock-oauth-code",
                    "consentGiven": True,
                }
            ),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(connected.status_code, 201, connected.content)
        connection_id = connected.json()["id"]
        self.assertTrue(
            PlatformConnectionRecord.objects.filter(
                id=connection_id,
                merchant_id=self.merchant_id,
                status="active",
            ).exists()
        )

        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        raw_body = json.dumps(
            {
                "platformConnectionId": connection_id,
                "messages": [
                    {
                        "id": "e2e-message-1",
                        "from": "customer-1",
                        "displayName": "Client",
                        "text": "je prends 3 sacs à 15000F",
                        "timestamp": timestamp,
                    }
                ],
            },
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(
            b"e2e-webhook-secret",
            timestamp.encode("ascii") + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
        webhook = self.client.post(
            "/api/v1/webhooks/whatsapp",
            data=raw_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )
        self.assertEqual(webhook.status_code, 200, webhook.content)
        self.assertEqual(webhook.json()["messageCount"], 1)

        platform_publisher = RedisStreamEventPublisher(self.redis, self.platform_stream)
        self.assertEqual(
            OutboxRelayWorker(PlatformOutboxRecord, platform_publisher, 10, 1, 30).publish_batch(),
            2,
        )
        rules_group = f"rules-{uuid4()}"
        crm_group = f"crm-{uuid4()}"
        rules_messages = self._consume(self.platform_stream, rules_group, "rules-engine")
        self._consume(self.platform_stream, crm_group, "crm")
        self.assertEqual(rules_messages, 2)
        self.assertEqual(
            list(RulesOutboxRecord.objects.values_list("event_type", flat=True)),
            ["MessageEvaluated"],
        )

        order_detection_group = f"order-detection-{uuid4()}"
        self.assertEqual(
            OutboxRelayWorker(
                RulesOutboxRecord,
                RedisStreamEventPublisher(self.redis, self.rules_stream),
                10,
                1,
                30,
            ).publish_batch(),
            1,
        )
        self._consume(self.rules_stream, order_detection_group, "order-detection")

        order = OrderRecord.objects.get(merchant_id=self.merchant_id)
        self.assertEqual(order.status, "pending_payment")
        self.assertEqual(order.detected_amount, 15000)
        OrderRecord.objects.filter(id=order.id).update(
            created_at=django_timezone.now() - timedelta(hours=2)
        )

        dashboard = self.client.get(
            "/api/v1/dashboard/dormant-money?olderThanHours=1", **self.headers
        )

        self.assertEqual(dashboard.status_code, 200, dashboard.content)
        payload = dashboard.json()
        self.assertEqual(
            payload["totalDormantAmount"], {"amount": "15000.0000", "currency": "XOF"}
        )
        contact = ContactRecord.objects.get(merchant_id=self.merchant_id)
        self.assertEqual(contact.external_identifier, "customer-1")

    def _issue_access_token(self):
        from contexts.identity.infrastructure.adapters.django_security_services import (
            DjangoTokenService,
        )

        return DjangoTokenService().issue_tokens(self.user.id)["accessToken"]

    def _consume(self, stream_name, group_name, consumer_context):
        self.redis.xgroup_create(stream_name, group_name, id="0-0", mkstream=True)
        self._groups.append((stream_name, group_name))
        handler = self._handler(consumer_context)
        failures = []

        def checked_handler(envelope):
            try:
                handler(envelope)
            except Exception as error:
                frames = [frame.name for frame in traceback.extract_tb(error.__traceback__)]
                failures.append((type(error).__name__, frames))
                raise

        worker = RedisStreamConsumerWorker(
            self.redis,
            stream_name,
            group_name,
            f"e2e-{uuid4()}",
            checked_handler,
            settings.STREAM_CLAIM_IDLE_MS,
            settings.STREAM_MAX_DELIVERIES,
        )
        with override_settings(CONSUMER_CONTEXT=consumer_context):
            processed = worker.process_once(block_ms=1)
        self.assertEqual(failures, [], f"{consumer_context} handler error types: {failures}")
        return processed

    @staticmethod
    def _handler(consumer_context):
        from piedlens_platform.event_bus.handlers import (
            handle_message_evaluated,
            handle_message_received,
        )

        return handle_message_evaluated if consumer_context == "order-detection" else handle_message_received
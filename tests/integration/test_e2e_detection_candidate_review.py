import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

import redis
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone as django_timezone

from contexts.access_control.infrastructure.persistence.models import (
    RoleAssignmentRecord,
    RoleRecord,
)
from contexts.identity.infrastructure.persistence.models import MerchantRecord, UserRecord
from contexts.order_detection.infrastructure.persistence.models import (
    DetectionCandidateRecord,
    OrderRecord,
    OutboxEventRecord as OrderDetectionOutboxRecord,
)
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


class DetectionCandidateReviewE2ETests(TestCase):
    def setUp(self):
        call_command("seed_billing_plans", verbosity=0)
        self.redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
        self.redis.ping()
        self.platform_stream = f"test:e2e:candidate:platform:{uuid4()}"
        self.rules_stream = f"test:e2e:candidate:rules:{uuid4()}"
        self.order_stream = f"test:e2e:candidate:orders:{uuid4()}"
        self.groups = []
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
            name="Candidate review merchant",
            country="CI",
            preferred_language="fr",
            currency="XOF",
            subscription_plan="starter",
            created_at=now,
        )
        role = RoleRecord.objects.create(
            id=uuid4(),
            name=f"E2E reviewer {uuid4()}",
            permissions=["platform.connect", "order.review"],
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
        self.headers = {
            "HTTP_AUTHORIZATION": f"Bearer {self._issue_access_token()}",
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
                    "pattern": ["je prends"],
                    "weight": 20,
                    "is_active": True,
                    "currency": None,
                    "config": {"intent": "purchase"},
                },
                {
                    "rule_id": str(uuid4()),
                    "rule_type": "AmountPattern",
                    "language": "fr",
                    "pattern": {
                        "regex": r"(?P<amount>\d+)F",
                        "groupSeparator": "",
                        "decimalSeparator": ",",
                    },
                    "weight": 80,
                    "is_active": True,
                    "currency": "XOF",
                    "config": {},
                },
                {
                    "rule_id": str(uuid4()),
                    "rule_type": "KeywordMatch",
                    "language": "fr",
                    "pattern": ["terme de commande confirmé"],
                    "weight": 80,
                    "is_active": True,
                    "currency": None,
                    "config": {},
                },
            ],
        )

    def tearDown(self):
        for stream_name, group_name in self.groups:
            try:
                self.redis.xgroup_destroy(stream_name, group_name)
            except redis.RedisError:
                pass
        self.redis.delete(self.platform_stream, self.rules_stream, self.order_stream)

    @override_settings(
        PLATFORM_WEBHOOK_SECRETS={"whatsapp": "candidate-e2e-secret"},
        PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=300,
    )
    def test_low_confidence_candidate_is_promoted_only_after_review_api(self):
        connected = self.client.post(
            "/api/v1/platform-connections",
            data=json.dumps(
                {
                    "platformType": "whatsapp",
                    "oauthCode": "candidate-e2e-oauth",
                    "consentGiven": True,
                }
            ),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(connected.status_code, 201, connected.content)
        self._send_message(connected.json()["id"])

        platform_count = OutboxRelayWorker(
            PlatformOutboxRecord,
            RedisStreamEventPublisher(self.redis, self.platform_stream),
            10,
            1,
            30,
        ).publish_batch()
        self.assertEqual(platform_count, 2)
        self.assertEqual(
            self._consume(self.platform_stream, "rules-engine", "rules-engine"), 2
        )
        rules_count = OutboxRelayWorker(
            RulesOutboxRecord,
            RedisStreamEventPublisher(self.redis, self.rules_stream),
            10,
            1,
            30,
        ).publish_batch()
        self.assertEqual(rules_count, 1)
        self._consume(self.rules_stream, "order-detection", "order-detection")

        candidate = DetectionCandidateRecord.objects.get(merchant_id=self.merchant_id)
        self.assertEqual(candidate.status, "pending_review")
        self.assertEqual(candidate.confidence_score, 56)
        self.assertFalse(OrderRecord.objects.filter(merchant_id=self.merchant_id).exists())

        candidates = self.client.get("/api/v1/detection-candidates", **self.headers)
        self.assertEqual(candidates.status_code, 200, candidates.content)
        self.assertEqual(candidates.json()["totalCount"], 1)
        decision = self.client.post(
            f"/api/v1/detection-candidates/{candidate.id}/decision",
            data=json.dumps({"decision": "validate"}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(decision.status_code, 200, decision.content)
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, "promoted")

        promoted_count = OutboxRelayWorker(
            OrderDetectionOutboxRecord,
            RedisStreamEventPublisher(self.redis, self.order_stream),
            10,
            1,
            30,
        ).publish_batch()
        self.assertGreaterEqual(promoted_count, 2)
        stream_entries = self.redis.xrange(self.order_stream)
        self.assertTrue(
            any(
                json.loads(fields[b"envelope"])["eventType"]
                == "DetectionCandidatePromoted"
                for _, fields in stream_entries
            )
        )
        self._consume_with_handler(
            self.order_stream,
            "order-detection-promotion",
            "order-detection",
            "piedlens_platform.event_bus.handlers.handle_detection_candidate_promoted",
            promoted_count,
        )
        order = OrderRecord.objects.get(merchant_id=self.merchant_id)
        self.assertEqual(order.status, "pending_payment")
        self.assertEqual(order.source_candidate_id, candidate.id)

    def _send_message(self, connection_id):
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        body = json.dumps(
            {
                "platformConnectionId": connection_id,
                "messages": [
                    {
                        "id": "candidate-message-1",
                        "from": "candidate-customer",
                        "displayName": "Client",
                        "text": "je prends 3 sacs à 15000F",
                        "timestamp": timestamp,
                    }
                ],
            },
            separators=(",", ":"),
        ).encode()
        signature = hmac.new(
            b"candidate-e2e-secret",
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        response = self.client.post(
            "/api/v1/webhooks/whatsapp",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def _issue_access_token(self):
        from contexts.identity.infrastructure.adapters.django_security_services import (
            DjangoTokenService,
        )

        return DjangoTokenService().issue_tokens(self.user.id)["accessToken"]

    def _consume(self, stream_name, group_name, consumer_context):
        self.redis.xgroup_create(stream_name, group_name, id="0-0", mkstream=True)
        self.groups.append((stream_name, group_name))
        from piedlens_platform.event_bus.handlers import (
            handle_message_evaluated,
            handle_message_received,
        )

        handler = handle_message_evaluated if consumer_context == "order-detection" else handle_message_received
        worker = RedisStreamConsumerWorker(
            self.redis,
            stream_name,
            group_name,
            f"candidate-e2e-{uuid4()}",
            handler,
            settings.STREAM_CLAIM_IDLE_MS,
            settings.STREAM_MAX_DELIVERIES,
        )
        with override_settings(CONSUMER_CONTEXT=consumer_context):
            processed = worker.process_once(block_ms=1)
        self.assertEqual(processed, 2 if stream_name == self.platform_stream else 1)
        return processed

    def _consume_with_handler(
        self, stream_name, group_name, consumer_context, handler_path, expected_count
    ):
        self.redis.xgroup_create(stream_name, group_name, id="0-0", mkstream=True)
        self.groups.append((stream_name, group_name))
        module_name, attribute = handler_path.rsplit(".", 1)
        from importlib import import_module

        handler = getattr(import_module(module_name), attribute)
        failures = []

        def checked_handler(envelope):
            try:
                handler(envelope)
            except Exception as error:
                failures.append((type(error).__name__, str(error)))
                raise

        worker = RedisStreamConsumerWorker(
            self.redis,
            stream_name,
            group_name,
            f"candidate-e2e-promotion-{uuid4()}",
            checked_handler,
            settings.STREAM_CLAIM_IDLE_MS,
            settings.STREAM_MAX_DELIVERIES,
        )
        with override_settings(CONSUMER_CONTEXT=consumer_context):
            processed = worker.process_once(block_ms=1)
        self.assertEqual(failures, [])
        self.assertEqual(processed, expected_count)
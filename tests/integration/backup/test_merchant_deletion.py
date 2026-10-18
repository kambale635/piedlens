import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings

from contexts.backup.infrastructure.persistence.django_object_storage import DjangoObjectStorage
from contexts.backup.infrastructure.persistence.models import (
    BackupObjectRecord,
    BackupSnapshotRecord,
    MerchantDeletionTokenRecord,
    OutboxEventRecord,
    S3ObjectDeletionRecord,
)
from contexts.backup.application.use_cases.delete_all_merchant_data_use_case import (
    DeleteAllMerchantDataUseCase,
)
from contexts.backup.infrastructure.messaging.django_backup_outbox import DjangoBackupOutbox
from contexts.backup.infrastructure.persistence.django_backup_repository import DjangoBackupRepository
from contexts.backup.infrastructure.persistence.django_unit_of_work import DjangoBackupUnitOfWork
from contexts.backup.infrastructure.persistence.s3_object_storage import S3ObjectStorage
from contexts.backup.infrastructure.adapters.system_backup_clock import SystemBackupClock
from contexts.identity.infrastructure.persistence.models import UserRecord


class AllowMerchantDeletion:
    def can(self, **kwargs):
        return kwargs["permission"] == "merchant.delete_data"


class ValidDeletionToken:
    def consume(self, merchant_id, token):
        return token == "valid"

    def is_valid(self, merchant_id, token):
        return token == "valid"


class BackupMerchantDeletionIntegrationTests(TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.user_id = uuid4()
        UserRecord.objects.create(
            id=self.user_id,
            phone_number="+14155550991",
            password_hash=make_password("current-password"),
            status="active",
            created_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        )
        self.enterContext(
            override_settings(
                PIEDLENS_AUTHENTICATOR=self._authenticate,
                PIEDLENS_PERMISSION_CHECKER=AllowMerchantDeletion(),
                BACKUP_OBJECT_STORAGE_BACKEND="postgres",
            )
        )

    def _authenticate(self, request):
        return SimpleNamespace(
            id=self.user_id,
            merchant_id=self.merchant_id,
            is_authenticated=True,
        )

    def test_request_reauthenticates_and_deletion_consumes_token_once(self):
        storage = DjangoObjectStorage()
        reference = storage.store({"messages": [{"text": "private"}]})
        BackupSnapshotRecord.objects.create(
            id=uuid4(),
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            snapshot_date=datetime(2026, 10, 18, tzinfo=timezone.utc),
            status="succeeded",
            data_integrity_hash="a" * 64,
            storage_reference=reference,
            message_count=1,
            media_count=0,
        )
        request_response = self.client.post(
            f"/api/v1/merchants/{self.merchant_id}/data/deletion-request",
            data=json.dumps({"password": "current-password"}),
            content_type="application/json",
        )

        self.assertEqual(request_response.status_code, 201, request_response.content)
        raw_token = request_response.json()["confirmationToken"]
        token_record = MerchantDeletionTokenRecord.objects.get(merchant_id=self.merchant_id)
        self.assertNotEqual(token_record.token_hash, raw_token)
        self.assertEqual(
            token_record.token_hash,
            hashlib.sha256(raw_token.encode()).hexdigest(),
        )

        delete_response = self.client.delete(
            f"/api/v1/merchants/{self.merchant_id}/data",
            data=json.dumps({"confirmationToken": raw_token}),
            content_type="application/json",
        )

        self.assertEqual(delete_response.status_code, 200, delete_response.content)
        token_record.refresh_from_db()
        self.assertIsNotNone(token_record.consumed_at)
        self.assertFalse(BackupSnapshotRecord.objects.filter(merchant_id=self.merchant_id).exists())
        self.assertFalse(BackupObjectRecord.objects.filter(id=reference).exists())
        self.assertEqual(OutboxEventRecord.objects.filter(event_type="MerchantDataDeleted").count(), 1)

        replay_response = self.client.delete(
            f"/api/v1/merchants/{self.merchant_id}/data",
            data=json.dumps({"confirmationToken": raw_token}),
            content_type="application/json",
        )
        self.assertEqual(replay_response.status_code, 403)
        self.assertEqual(replay_response.json()["errorCode"], "INVALID_CONFIRMATION_TOKEN")
        self.assertEqual(OutboxEventRecord.objects.filter(event_type="MerchantDataDeleted").count(), 1)

    def test_wrong_password_returns_catalogued_401_without_issuing_token(self):
        response = self.client.post(
            f"/api/v1/merchants/{self.merchant_id}/data/deletion-request",
            data=json.dumps({"password": "wrong-password"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["errorCode"], "INVALID_CREDENTIALS")
        self.assertFalse(MerchantDeletionTokenRecord.objects.exists())

    def test_route_rejects_a_different_merchant_than_the_authenticated_tenant(self):
        response = self.client.post(
            f"/api/v1/merchants/{uuid4()}/data/deletion-request",
            data=json.dumps({"password": "current-password"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errorCode"], "TENANT_REQUIRED")
        self.assertFalse(MerchantDeletionTokenRecord.objects.exists())

    def test_s3_references_are_queued_without_remote_calls_inside_deletion(self):
        class Client:
            def __init__(self):
                self.deleted = []

            def delete_object(self, **kwargs):
                self.deleted.append(kwargs)

        client = Client()
        reference = "remote-snapshot-key"
        BackupSnapshotRecord.objects.create(
            id=uuid4(),
            merchant_id=self.merchant_id,
            platform_connection_id=uuid4(),
            snapshot_date=datetime(2026, 10, 18, tzinfo=timezone.utc),
            status="succeeded",
            data_integrity_hash="b" * 64,
            storage_reference=reference,
            message_count=0,
            media_count=0,
        )
        use_case = DeleteAllMerchantDataUseCase(
            backups=DjangoBackupRepository(),
            storage=S3ObjectStorage(client=client),
            token_verifier=ValidDeletionToken(),
            unit_of_work=DjangoBackupUnitOfWork(),
            outbox=DjangoBackupOutbox(),
            clock=SystemBackupClock(),
        )

        use_case.execute(self.merchant_id, "valid")

        self.assertEqual(client.deleted, [])
        self.assertEqual(
            S3ObjectDeletionRecord.objects.filter(reference=reference).count(),
            1,
        )
        self.assertFalse(BackupSnapshotRecord.objects.filter(merchant_id=self.merchant_id).exists())
        self.assertEqual(OutboxEventRecord.objects.filter(event_type="MerchantDataDeleted").count(), 1)
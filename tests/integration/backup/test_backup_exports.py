import json
import base64
from io import StringIO
from urllib.parse import urlparse, parse_qs

from django.core.management import call_command
from django.test import TestCase, override_settings

from contexts.backup.infrastructure.persistence.django_object_storage import DjangoObjectStorage
from contexts.backup.infrastructure.persistence.models import BackupObjectRecord, S3ObjectDeletionRecord
from contexts.backup.infrastructure.persistence.s3_object_deletion_worker import (
    S3ObjectDeletionWorker,
)
from contexts.backup.infrastructure.persistence.s3_object_storage import S3ObjectStorage


class BackupExportIntegrationTests(TestCase):
    def test_backup_payload_rotation_reencrypts_objects_without_changing_references(self):
        first_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        second_key = base64.urlsafe_b64encode(b"b" * 32).decode()
        with override_settings(
            BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION="v1",
            BACKUP_DATA_ENCRYPTION_KEYS={"v1": first_key},
        ):
            storage = DjangoObjectStorage()
            reference = storage.store({"content": "snapshot data"})
        output = StringIO()

        with override_settings(
            BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION="v2",
            BACKUP_DATA_ENCRYPTION_KEYS={"v1": first_key, "v2": second_key},
        ):
            call_command("rotate_backup_payloads", stdout=output)
            stored = BackupObjectRecord.objects.get(id=reference)
            self.assertEqual(DjangoObjectStorage().retrieve(reference), {"content": "snapshot data"})

        self.assertEqual(stored.payload["_piedlens_encrypted_backup"], "v2")
        self.assertEqual(output.getvalue(), "Rotated 1 backup object(s).\n")

    def test_database_object_storage_encrypts_payload_at_rest(self):
        from contexts.backup.infrastructure.persistence.models import BackupObjectRecord

        payload = {"messages": [{"text": "private snapshot body"}]}
        storage = DjangoObjectStorage()
        reference = storage.store(payload)
        stored = BackupObjectRecord.objects.get(id=reference).payload

        self.assertNotIn("private snapshot body", json.dumps(stored))
        self.assertIn("_piedlens_encrypted_backup", stored)
        self.assertEqual(storage.retrieve(reference), payload)

    @override_settings(
        BACKUP_EXPORT_SIGNING_SECRET="integration-signing-secret",
        BACKUP_EXPORT_BASE_URL="http://testserver/api/v1/backups/objects",
    )
    def test_signed_url_retrieves_only_the_signed_object(self):
        storage = DjangoObjectStorage()
        reference = storage.store({"json": "{}", "csv": "record_type,record"})
        signed_url = storage.generate_signed_url(reference, 15)
        parsed = urlparse(signed_url)
        query = parse_qs(parsed.query)

        self.assertTrue(
            storage.verify_signed_url(reference, query["expires"][0], query["signature"][0])
        )
        response = self.client.get(signed_url.replace("http://testserver", ""))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"json": "{}", "csv": "record_type,record"})

    @override_settings(BACKUP_EXPORT_SIGNING_SECRET="integration-signing-secret")
    def test_unsigned_export_object_request_is_rejected(self):
        reference = DjangoObjectStorage().store({"private": "data"})

        response = self.client.get(f"/api/v1/backups/objects/{reference}?expires=1&signature=invalid")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errorCode"], "INVALID_EXPORT_SIGNATURE")

    @override_settings(BACKUP_S3_BUCKET="backup-test")
    def test_s3_delete_is_queued_and_worker_retries_without_losing_job(self):
        class Client:
            exceptions = type("Exceptions", (), {"NoSuchKey": KeyError})

            def __init__(self):
                self.attempts = 0

            def delete_object(self, **kwargs):
                self.attempts += 1
                if self.attempts == 1:
                    raise ConnectionError("temporary S3 outage")

        client = Client()
        storage = S3ObjectStorage(client=client)
        storage.delete("snapshot-object")
        record = S3ObjectDeletionRecord.objects.get(reference="snapshot-object")
        self.assertEqual(client.attempts, 0)

        worker = S3ObjectDeletionWorker(storage, 10, 0, 0)
        deleted, failed = worker.process_once()
        record.refresh_from_db()
        self.assertEqual((deleted, failed), (0, 1))
        self.assertEqual(record.attempts, 1)
        self.assertEqual(record.last_error_type, "ConnectionError")

        deleted, failed = worker.process_once()
        self.assertEqual((deleted, failed), (1, 0))
        self.assertFalse(S3ObjectDeletionRecord.objects.filter(reference="snapshot-object").exists())

    @override_settings(
        BACKUP_S3_BUCKET="backup-test",
        BACKUP_S3_REGION="eu-west-1",
    )
    def test_s3_storage_uploads_encrypted_object_and_returns_signed_url(self):
        class Body:
            def read(self):
                return b'{"messages": []}'

        class Client:
            exceptions = type("Exceptions", (), {"NoSuchKey": KeyError})

            def put_object(self, **kwargs):
                self.put_call = kwargs

            def get_object(self, **kwargs):
                return {"Body": Body()}

            def generate_presigned_url(self, operation, Params, ExpiresIn):
                return f"https://s3.invalid/{Params['Key']}?expires={ExpiresIn}"

        client = Client()
        storage = S3ObjectStorage(client=client)
        reference = storage.store({"messages": []})

        self.assertEqual(client.put_call["Bucket"], "backup-test")
        self.assertEqual(client.put_call["ServerSideEncryption"], "AES256")
        self.assertIn("_piedlens_encrypted_backup", json.loads(client.put_call["Body"]))
        self.assertEqual(storage.retrieve(reference), {"messages": []})
        self.assertEqual(
            storage.generate_signed_url(reference, 15),
            f"https://s3.invalid/{reference}?expires=900",
        )
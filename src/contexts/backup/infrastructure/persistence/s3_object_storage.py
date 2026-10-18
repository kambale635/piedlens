"""S3-compatible IObjectStorage adapter for production backup objects."""

import json
from uuid import uuid4

from django.conf import settings

from ...application.exceptions import BackupSnapshotNotFoundException
from .models import S3ObjectDeletionRecord
from .django_object_storage import DjangoObjectStorage
from .django_backup_payload_cipher import DjangoBackupPayloadCipher


class S3ObjectStorage:
    """Store JSON backup objects in an S3-compatible bucket using presigned URLs."""

    def __init__(self, client=None, payload_cipher=None) -> None:
        self._bucket = settings.BACKUP_S3_BUCKET
        self._payload_cipher = payload_cipher or DjangoBackupPayloadCipher()
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=settings.BACKUP_S3_ENDPOINT_URL or None,
                region_name=settings.BACKUP_S3_REGION,
                aws_access_key_id=settings.BACKUP_S3_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.BACKUP_S3_SECRET_ACCESS_KEY or None,
                use_ssl=settings.BACKUP_S3_USE_TLS,
                verify=settings.BACKUP_S3_VERIFY_TLS,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )
        self._client = client

    def store(self, file: object) -> str:
        """Serialize a snapshot/export payload and persist it under an opaque key."""
        key = str(uuid4())
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=json.dumps(self._payload_cipher.encrypt(file)).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        return key

    def retrieve(self, reference: str) -> object:
        """Load and decode one object by opaque storage reference."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=reference)
        except self._client.exceptions.NoSuchKey as error:
            raise BackupSnapshotNotFoundException("Stored backup object was not found.") from error
        envelope = json.loads(response["Body"].read())
        payload = self._payload_cipher.decrypt(envelope)
        if self._payload_cipher.key_version(envelope) != self._payload_cipher.active_version:
            self._client.put_object(
                Bucket=self._bucket,
                Key=reference,
                Body=json.dumps(self._payload_cipher.encrypt(payload)).encode("utf-8"),
                ContentType="application/json",
                ServerSideEncryption="AES256",
            )
        return payload

    def rotate_object(self, reference: str) -> bool:
        """Re-encrypt one remote object in place while retaining its storage reference."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=reference)
        except self._client.exceptions.NoSuchKey:
            return False
        envelope = json.loads(response["Body"].read())
        if self._payload_cipher.key_version(envelope) == self._payload_cipher.active_version:
            return False
        payload = self._payload_cipher.decrypt(envelope)
        self._client.put_object(
            Bucket=self._bucket,
            Key=reference,
            Body=json.dumps(self._payload_cipher.encrypt(payload)).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        return True

    def generate_signed_url(self, reference: str, expires_in_minutes: int) -> str:
        """Return an S3-compatible presigned GET URL with bounded expiry."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": reference},
            ExpiresIn=expires_in_minutes * 60,
        )

    def delete(self, reference: str) -> None:
        """Queue an idempotent remote delete in the active Backup transaction (INV-BK-06)."""
        S3ObjectDeletionRecord.objects.get_or_create(reference=reference)

    def delete_now(self, reference: str) -> None:
        """Delete an object remotely; reserved for the retry worker outside DB transactions."""
        self._client.delete_object(Bucket=self._bucket, Key=reference)


def configured_object_storage():
    """Select PostgreSQL development storage or configured S3-compatible storage."""
    backend = settings.BACKUP_OBJECT_STORAGE_BACKEND
    if backend == "postgres":
        return DjangoObjectStorage()
    if backend == "s3":
        if not settings.BACKUP_S3_BUCKET:
            raise RuntimeError("BACKUP_S3_BUCKET is required when S3 storage is selected.")
        return S3ObjectStorage()
    raise RuntimeError(f"Unsupported BACKUP_OBJECT_STORAGE_BACKEND: {backend}")
from urllib.parse import urlparse, parse_qs

from django.test import TestCase, override_settings

from contexts.backup.infrastructure.persistence.django_object_storage import DjangoObjectStorage


class BackupExportIntegrationTests(TestCase):
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
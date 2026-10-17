import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.backup.application.exceptions import (
    BackupConsentRequiredException,
    InvalidConfirmationTokenException,
)
from contexts.backup.application.use_cases.create_snapshot_use_case import CreateSnapshotUseCase
from contexts.backup.application.use_cases.check_account_health_use_case import (
    CheckAccountHealthUseCase,
)
from contexts.backup.application.use_cases.delete_all_merchant_data_use_case import (
    DeleteAllMerchantDataUseCase,
)
from contexts.backup.application.use_cases.get_backup_export_use_case import (
    GetBackupExportUseCase,
)
from contexts.backup.application.use_cases.list_backups_use_case import ListBackupsUseCase
from contexts.backup.application.use_cases.restore_from_snapshot_use_case import (
    RestoreFromSnapshotUseCase,
)
from contexts.backup.domain.entities.backup_snapshot import BackupSnapshot
from contexts.backup.domain.events.backup_events import BackupCompleted, BackupFailed
from contexts.backup.domain.value_objects.snapshot_status import SnapshotStatus


class FakeBackupRepository:
    def __init__(self, snapshots=()):
        self.snapshots = list(snapshots)
        self.exports = {}
        self.deleted_references = []

    def save_snapshot(self, snapshot):
        self.snapshots.append(snapshot)

    def find_latest_successful(self, connection_id):
        candidates = [
            snapshot
            for snapshot in self.snapshots
            if snapshot.platform_connection_id == connection_id
            and snapshot.status is SnapshotStatus.SUCCEEDED
        ]
        return max(candidates, key=lambda item: item.snapshot_date) if candidates else None

    def find_by_date_range(self, connection_id, from_date, to_date):
        return [
            snapshot
            for snapshot in self.snapshots
            if snapshot.platform_connection_id == connection_id
            and from_date <= snapshot.snapshot_date <= to_date
        ]

    def list_snapshots(self, merchant_id, connection_id, offset, limit):
        selected = [item for item in self.snapshots if item.merchant_id == merchant_id]
        if connection_id:
            selected = [item for item in selected if item.platform_connection_id == connection_id]
        return selected[offset:offset + limit], len(selected)

    def delete_for_merchant(self, merchant_id):
        self.deleted_references = [
            item.storage_reference for item in self.snapshots
            if item.merchant_id == merchant_id and item.storage_reference
        ]
        self.snapshots = [item for item in self.snapshots if item.merchant_id != merchant_id]
        return self.deleted_references

    def save_export(self, export):
        self.exports[export["id"]] = export

    def find_export(self, merchant_id, export_job_id):
        export = self.exports.get(export_job_id)
        return export if export and export["merchant_id"] == merchant_id else None


class FakeStorage:
    def __init__(self, fail_store=False):
        self.objects = {}
        self.fail_store = fail_store
        self.deleted = []

    def store(self, file):
        if self.fail_store:
            raise OSError("storage unavailable")
        reference = str(uuid4())
        self.objects[reference] = file
        return reference

    def retrieve(self, reference):
        return self.objects[reference]

    def generate_signed_url(self, reference, expires_in_minutes):
        return f"https://storage.invalid/{reference}?ttl={expires_in_minutes}"

    def delete(self, reference):
        self.deleted.append(reference)
        self.objects.pop(reference, None)


class FakeUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class FakeOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class FakeClock:
    def now_utc(self):
        return datetime(2026, 10, 17, tzinfo=timezone.utc)


class BackupUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.merchant_id = uuid4()
        self.connection_id = uuid4()

    def test_snapshot_requires_explicit_consent_before_reading_data(self):
        reader = type("Consent", (), {"consent_for": lambda *_: (self.merchant_id, None)})()
        message_reader = type("Messages", (), {"read_messages": lambda *_: self.fail("read")})()
        use_case = CreateSnapshotUseCase(
            FakeBackupRepository(), FakeStorage(), reader, message_reader,
            type("Contacts", (), {"read_contacts": lambda *_: []})(),
            FakeUnitOfWork(), FakeOutbox(), FakeClock(),
        )

        with self.assertRaises(BackupConsentRequiredException):
            use_case.execute(self.connection_id)

    def test_snapshot_is_incremental_hashed_and_completed_atomically(self):
        previous = BackupSnapshot.succeeded(
            self.merchant_id,
            self.connection_id,
            datetime(2026, 10, 16, tzinfo=timezone.utc),
            "previous-hash",
            "previous-object",
            1,
        )
        repository = FakeBackupRepository([previous])
        storage = FakeStorage()
        outbox = FakeOutbox()
        observed_since = []

        class Messages:
            def read_messages(self, connection_id, since):
                observed_since.append(since)
                return [{"id": "new-message"}]

        use_case = CreateSnapshotUseCase(
            repository,
            storage,
            type("Consent", (), {"consent_for": lambda *_: (self.merchant_id, FakeClock().now_utc())})(),
            Messages(),
            type("Contacts", (), {"read_contacts": lambda *_: [{"id": "contact"}]})(),
            FakeUnitOfWork(),
            outbox,
            FakeClock(),
        )

        result = use_case.execute(self.connection_id)

        self.assertEqual(observed_since, [previous.snapshot_date])
        self.assertEqual(result["status"], "succeeded")
        snapshot = repository.snapshots[-1]
        payload = storage.objects[snapshot.storage_reference]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.assertEqual(snapshot.data_integrity_hash, hashlib.sha256(encoded.encode()).hexdigest())
        self.assertIsInstance(outbox.events[0], BackupCompleted)

    def test_storage_failure_never_marks_partial_snapshot_succeeded(self):
        repository = FakeBackupRepository()
        outbox = FakeOutbox()
        use_case = CreateSnapshotUseCase(
            repository,
            FakeStorage(fail_store=True),
            type("Consent", (), {"consent_for": lambda *_: (self.merchant_id, FakeClock().now_utc())})(),
            type("Messages", (), {"read_messages": lambda *_: [{"id": "message"}]})(),
            type("Contacts", (), {"read_contacts": lambda *_: []})(),
            FakeUnitOfWork(),
            outbox,
            FakeClock(),
        )

        result = use_case.execute(self.connection_id)

        self.assertEqual(result["status"], "failed")
        self.assertIs(repository.snapshots[-1].status, SnapshotStatus.FAILED)
        self.assertIsNone(repository.snapshots[-1].storage_reference)
        self.assertIsInstance(outbox.events[0], BackupFailed)

    def test_restore_creates_two_formats_and_expiring_export(self):
        snapshot = BackupSnapshot.succeeded(
            self.merchant_id,
            self.connection_id,
            FakeClock().now_utc(),
            "hash",
            "snapshot-reference",
            1,
        )
        repository = FakeBackupRepository([snapshot])
        storage = FakeStorage()
        storage.objects["snapshot-reference"] = {"messages": [{"id": "message"}], "contacts": []}
        use_case = RestoreFromSnapshotUseCase(
            repository, storage, FakeUnitOfWork(), FakeClock(), export_ttl_minutes=30
        )

        result = use_case.execute(self.connection_id, merchant_id=self.merchant_id)

        export = next(iter(repository.exports.values()))
        payload = storage.objects[export["storage_reference"]]
        self.assertEqual(result["status"], "processing")
        self.assertIn('"messages"', payload["json"])
        self.assertIn("record_type", payload["csv"])
        self.assertEqual(export["expires_at"], FakeClock().now_utc() + timedelta(minutes=30))

    def test_delete_requires_valid_second_confirmation_and_deletes_owned_objects(self):
        snapshot = BackupSnapshot.succeeded(
            self.merchant_id, self.connection_id, FakeClock().now_utc(), "hash", "object-1", 0
        )
        repository = FakeBackupRepository([snapshot])
        storage = FakeStorage()
        outbox = FakeOutbox()
        verifier = type("Verifier", (), {"is_valid": lambda self, merchant_id, token: token == "valid"})()
        use_case = DeleteAllMerchantDataUseCase(
            repository, storage, verifier, FakeUnitOfWork(), outbox, FakeClock()
        )

        with self.assertRaises(InvalidConfirmationTokenException):
            use_case.execute(self.merchant_id, "invalid")
        result = use_case.execute(self.merchant_id, "valid")

        self.assertEqual(result["deleted_at"], FakeClock().now_utc())
        self.assertEqual(storage.deleted, ["object-1"])
        self.assertEqual(repository.snapshots, [])
        self.assertEqual(len(outbox.events), 1)

    def test_list_backups_and_get_export_are_merchant_scoped(self):
        snapshot = BackupSnapshot.succeeded(
            self.merchant_id, self.connection_id, FakeClock().now_utc(), "hash", "object", 2
        )
        repository = FakeBackupRepository([snapshot])
        listed = ListBackupsUseCase(repository).execute(self.merchant_id)
        export_id = uuid4()
        repository.save_export(
            {
                "id": export_id,
                "merchant_id": self.merchant_id,
                "status": "ready",
                "download_url": "https://signed.invalid/export",
                "expires_at": FakeClock().now_utc(),
            }
        )

        export = GetBackupExportUseCase(repository).execute(self.merchant_id, export_id)

        self.assertEqual(listed["total_count"], 1)
        self.assertEqual(export["status"], "ready")
        self.assertIn("download_url", export)

    def test_health_check_enqueues_alert_only_for_non_healthy_connection(self):
        outbox = FakeOutbox()
        checker = type(
            "HealthChecker",
            (),
            {"check_account_status": lambda *_: ("at_risk", ["provider_warning"])},
        )()
        use_case = CheckAccountHealthUseCase(
            checker, FakeUnitOfWork(), outbox, FakeClock()
        )

        result = use_case.execute(self.connection_id)

        self.assertEqual(result["health_status"], "at_risk")
        self.assertEqual(len(outbox.events), 1)


if __name__ == "__main__":
    unittest.main()
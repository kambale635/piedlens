# Backup

Protects merchant data with consent-based incremental snapshots, hash verification, CSV/JSON exports, health checks, and double-confirmed deletion. The current object store is PostgreSQL-backed for local development; replace it with S3-compatible storage before production.

Reference: [docs/10-context-backup.md](../../../docs/10-context-backup.md).

Use Cases: `ListBackupsUseCase`, `GetBackupExportUseCase`, `CreateSnapshotUseCase`, `RestoreFromSnapshotUseCase`, `CheckAccountHealthUseCase`, and `DeleteAllMerchantDataUseCase` in [docs/15-use-cases-catalog.md](../../../docs/15-use-cases-catalog.md#contexte-backup).

Tests: `python manage.py test tests.unit.backup tests.integration.backup`.
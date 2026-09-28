# Backup

Protects merchant data with consent-based snapshots, restore, health checks, and deletion.

Reference: [docs/10-context-backup.md](../../../docs/10-context-backup.md).

Use Cases: CreateSnapshotUseCase, RestoreFromSnapshotUseCase, CheckAccountHealthUseCase, and DeleteAllMerchantDataUseCase in [docs/15-use-cases-catalog.md](../../../docs/15-use-cases-catalog.md#contexte-backup).

Tests: `docker compose run --rm django python manage.py test tests.unit.backup`.
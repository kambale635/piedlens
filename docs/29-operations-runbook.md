# Operations Runbook

## Health and metrics

- `GET /health/live` confirms only that the Django process responds; it does not probe dependencies.
- `GET /health/ready` checks PostgreSQL and Redis and returns `503` without exposing connection details if either probe fails.
- `GET /health/metrics` requires `Authorization: Bearer <HEALTH_METRICS_TOKEN>`. It reports per-context oldest unpublished Outbox age and Redis DLQ stream lengths. Alert thresholds are controlled by `HEALTH_OUTBOX_LAG_ALERT_SECONDS` and `HEALTH_DLQ_SIZE_ALERT_THRESHOLD`; `PIEDLENS_ALERT_HOOK` names a dotted callable that receives threshold alerts. Keep this route behind the deployment's internal metrics network as well as its bearer token.
- Application logs are JSON on stdout and include the correlation ID when available. Do not add request bodies, message text, credentials, payment data, or exception messages to log calls.

## Workers and shutdown

Workers stop accepting another batch after SIGTERM/SIGINT. The current batch finishes before exit; consumer acknowledgement follows handler commit, so an interrupted pending Redis event is reclaimable. Set the orchestrator termination grace period longer than the longest expected batch. Compose workers use a 60-second grace period.

## PostgreSQL backup

Use a managed secret store or a protected `PGPASSFILE`; do not put a database password on the command line or in `PGPASSWORD` in a shared process environment. Run the dump from a trusted host with network access to the database:

```bash
pg_dump --format=custom --no-owner --no-acl \
  --host "$POSTGRES_HOST" --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" --file "$BACKUP_FILE"
```

Record the encrypted artifact's checksum and retain it according to the deployment policy. Confirm the dump process exits successfully before marking the backup complete.

## PostgreSQL restore

Restore into an isolated database first. Confirm the target database and artifact before running `pg_restore`; the options below replace objects in the named target and must not be pointed at a live database without an approved maintenance window and verified backup.

```bash
pg_restore --clean --if-exists --no-owner --no-acl \
  --host "$POSTGRES_HOST" --username "$POSTGRES_USER" \
  --dbname "$RESTORE_DATABASE" "$BACKUP_FILE"
```

Run Django migrations/checks and the operational smoke tests against the restored instance. Verify row counts, tenant-scoped reads, Outbox backlog, and encrypted object retrieval before switching traffic.

## Sentry

`SENTRY_DSN` activates the optional SDK integration and `SENTRY_ENVIRONMENT` sets its environment label. The repository currently does not install `sentry-sdk`; configure neither variable until that dependency is explicitly approved and a staging project DSN is provisioned. Never place a DSN value in this runbook or in Git.
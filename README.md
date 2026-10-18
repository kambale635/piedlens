# Piedlens

Modular Django monolith following the bounded-context structure in `docs/05-module-structure.md`.

For session handoff and continuation, follow [METHODE_REPRISE.md](METHODE_REPRISE.md) before changing code.

## Local infrastructure

1. Copy `.env.example` to `.env` and set a local `POSTGRES_PASSWORD`.
2. Start the services with `docker compose up --build`.
3. The Django development server listens on `http://localhost:8000`.

Compose runs migrations once before the API and workers start. PostgreSQL object storage is the local default. To use an S3-compatible bucket, set `BACKUP_OBJECT_STORAGE_BACKEND=s3` and the `BACKUP_S3_*` variables in `.env`, then start the queued deletion worker with `docker compose --profile s3 up --build`.

PostgreSQL and Redis are only available on the Compose network. Do not reuse local development credentials in staging or production.
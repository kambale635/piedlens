# Piedlens

Modular Django monolith following the bounded-context structure in `docs/05-module-structure.md`.

For session handoff and continuation, follow [METHODE_REPRISE.md](METHODE_REPRISE.md) before changing code.

## Local infrastructure

1. Copy `.env.example` to `.env` and set a local `POSTGRES_PASSWORD`.
2. Start the services with `docker compose up --build`.
3. The Django development server listens on `http://localhost:8000`.

PostgreSQL and Redis are only available on the Compose network. Do not reuse local development credentials in staging or production.
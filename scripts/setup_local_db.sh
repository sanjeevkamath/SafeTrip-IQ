#!/usr/bin/env bash
# Fixed Compose target: never reads a production connection URL or .env file.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose up -d --wait db
docker compose exec -T db psql -U safetrip_admin -d safetrip < db/local/bootstrap.sql
SAFETRIP_MIGRATION_URL='postgresql+psycopg://safetrip_migrator:migrator_local_only@127.0.0.1:55432/safetrip' \
    UV_PROJECT_ENVIRONMENT=.local/database-venv uv run --frozen --only-group database alembic upgrade head
docker compose exec -T -e PGPASSWORD=writer_local_only db \
    psql -h 127.0.0.1 -U safetrip_writer -d safetrip < db/local/seed.sql

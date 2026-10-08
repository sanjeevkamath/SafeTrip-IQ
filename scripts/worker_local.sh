#!/usr/bin/env bash
# Explicit local destination, even if root .env contains Supabase credentials.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export SAFETRIP_DB_BACKEND=postgres
export SAFETRIP_DATABASE_URL='postgresql+psycopg://safetrip_writer:writer_local_only@127.0.0.1:55432/safetrip'
exec uv run --frozen safetrip "$@"

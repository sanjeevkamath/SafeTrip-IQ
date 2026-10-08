#!/usr/bin/env bash
# Run the same checks as GitHub Actions from any working directory.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
# Use the project's managed Python without installing the full ML environment.
uv run --isolated --no-project --managed-python --python 3.11 python -m unittest discover -s tests -v
uv run --isolated --no-project --managed-python --python 3.11 python -m unittest discover -s db/tests -v
uv run --isolated --no-project --managed-python --python 3.11 python -m scripts.verify_baseline

cd frontend
export NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co
export NEXT_PUBLIC_SUPABASE_ANON_KEY=ci-placeholder
export NEXT_TELEMETRY_DISABLED=1
npm ci
npm run audit:production
npx tsc --noEmit
npm run lint
npm run build

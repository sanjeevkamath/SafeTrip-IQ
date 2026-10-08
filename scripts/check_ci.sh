#!/usr/bin/env bash
# Run the same checks as GitHub Actions from any working directory.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
# A disposable environment verifies the package without installing the ML stack.
uv venv --clear --managed-python --python 3.11 .local/ci-python
uv pip install --python .local/ci-python/bin/python --no-deps .
.local/ci-python/bin/safetrip --help
.local/ci-python/bin/python -m unittest discover -s tests -v
.local/ci-python/bin/python -m unittest discover -s db/tests -v
.local/ci-python/bin/python -m scripts.verify_baseline

cd frontend
export NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co
export NEXT_PUBLIC_SUPABASE_ANON_KEY=ci-placeholder
export NEXT_TELEMETRY_DISABLED=1
npm ci
npm run audit:production
npx tsc --noEmit
npm run lint
npm run test:queries
npm run build

#!/usr/bin/env bash
# Run the same checks as GitHub Actions from any working directory.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s db/tests -v
python3 -m scripts.verify_baseline

cd frontend
export NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co
export NEXT_PUBLIC_SUPABASE_ANON_KEY=ci-placeholder
export NEXT_TELEMETRY_DISABLED=1
npm ci
npx tsc --noEmit
npm run lint
npm run build

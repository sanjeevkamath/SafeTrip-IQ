#!/usr/bin/env bash
# Integration checks against the fixed local Compose database only.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bash scripts/setup_local_db.sh
uv pip install --python .local/database-venv/bin/python --no-deps .
.local/database-venv/bin/python -m unittest discover -s db/integration -v

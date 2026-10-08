#!/usr/bin/env bash
# Disposable local fixtures only; no checkpoint required for this smoke test.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose build web migrate worker
docker compose up -d --wait --wait-timeout 180 web
docker compose run --rm --no-deps --entrypoint python worker -c \
  'import os, importlib.util, torch; assert os.getuid() != 0; assert torch.version.cuda is None; assert not torch.cuda.is_available(); assert all(importlib.util.find_spec(name) is None for name in ("datasets", "matplotlib", "accelerate", "pandas", "sklearn")); print("Non-root CPU-only worker; research libraries excluded.")'
docker compose exec -T web node -e \
  'if(process.getuid()===0) process.exit(1); fetch("http://127.0.0.1:3000/api/countries-scores").then(async r=>{if(!r.ok) throw Error("API failed"); const rows=await r.json(); if(rows.length!==3 || !rows.some(r=>r.iso3==="CAN" && r.safe_trip_score===10)) throw Error("Unexpected seeded scores"); console.log("Non-root web reads seeded Postgres scores.");}).catch(()=>process.exit(1))'
docker compose run --rm --no-deps worker --help
output="/output/container-check-$(date +%s)-$$.json"
docker compose run --rm --no-deps worker ingest --input /app/fixtures/advisories.xml --output "$output" --write
docker compose exec -T -e PGPASSWORD=writer_local_only db \
  psql -h 127.0.0.1 -U safetrip_writer -d safetrip < db/local/seed.sql
echo "Container smoke checks passed; web remains available at http://localhost:3001."

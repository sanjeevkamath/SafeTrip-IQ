# Phase 4 checkpoint 6: full local dataset

The captured Supabase release has been validated and imported into a separate local database, `safetrip_full`, inside the existing Compose Postgres container. The normal `safetrip` database keeps three development fixtures for repeatable CI. Neither database is hosted Supabase.

## What was verified

The importer pins the reviewed snapshot manifest's SHA-256, checks every exported table's hash and row count, and verifies unique country identifiers and references. It also checks the frozen cluster CSV's hash before comparing its raw IDs with all stored risk tiers.

The historical mapping is exactly `1 → 0`, `0 → 1`, `3 → 2`, `2 → 3`, and `4 → 4`. All 168 records agree. The importer preserves these already-mapped database values and marks them as verified risk tiers; it never reruns the old non-idempotent remapping script. This verifies consistency with the frozen release, not scientific validity or a reproducible upstream data collection process.

All 212 captured final scores exactly match the current component formula. The resulting catalog has:

| Component availability | Countries |
| --- | ---: |
| Both | 164 |
| BERT only | 44 |
| Clustering only | 4 |
| Neither (NULL final score) | 38 |
| Total | 250 |

The snapshot contains 249 countries, 248 culture rows, 208 BERT rows, 168 clustering rows, and 209 advisories. One advisory identifies Kosovo as `XKX`, absent from the country catalog. The import adds only that identifier and its captured name; ISO2, continent, culture, and scores remain unset rather than inferred. It preserves all 209 advisories.

Every country gets a final-score row, including 38 NULL results. New import history records the snapshot identity, mapping, and catalog addition. BERT training provenance remains unknown, so imported predictions are not eligible for incremental reuse until a verified inference run produces them. The import does not mark historical advisories as freshly fetched; public refresh status remains unknown.

## Browse the full dataset

From the repository root:

```sh
cd frontend
npm run dev:full
```

If a development server is already running, stop it first or use the port printed by the new process. `npm run dev:local` returns to the three-country dataset. No environment file edits are needed.

## Reproduce the import

The full export remains ignored under `.local/baselines/20261008T032611470774Z`; a fresh clone needs that reviewed snapshot from the maintainer. Do not commit its full content merely to run tests. Synthetic and public-score regression fixtures cover import logic in CI.

Provision the standard local environment and install the current pipeline package without its ML dependencies:

```sh
bash scripts/setup_local_db.sh
uv pip install --python .local/database-venv/bin/python --no-deps .
.local/database-venv/bin/python -m scripts.import_local_baseline \
  --snapshot .local/baselines/20261008T032611470774Z \
  --output .local/demo/full-import-preview.json
```

The preview requires no database access. On a machine where `safetrip_full` is empty or absent, add `--write` with a new output path to create/migrate it and import in one application transaction. The script has a fixed loopback host, port, database name, and development roles; it never loads `.env` or accepts a production URL.

An existing populated database is deliberately refused. A rerun may add a failed run receipt but preserves application data. Schema provisioning is separate from the application transaction; a failed first import can leave an empty migrated database available for retry. The JSON report is written after commit; consult run history if saving that file fails.

The two-country advisory fixture is **not a complete feed for this full database**. The normal `scripts/worker_local.sh` continues to target the three-country database. A future full refresh must use a complete reviewed feed and an explicit `safetrip_full` worker configuration.

## Remaining Stage 4 work

Broader automated browser coverage and final CI/preview review remain. No new live-feed inference, retraining, hosted database migration, or AWS deployment is part of this import.

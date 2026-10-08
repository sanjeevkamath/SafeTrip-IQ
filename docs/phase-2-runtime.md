# Phase 2 — Runtime package and explicit commands

## Boundaries

```text
frontend/                         Next.js site; deployment root unchanged
pipeline/src/safetrip/
  cli.py                          Command parsing and explicit publication choice
  config.py                       Project paths and explicit environment loading
  jobs.py                         Orchestration and input validation
  ingestion/advisories.py          Fetching, parsing, legacy cleaning, country mapping
  inference/bert.py               Local model loading and predictions
  scoring/legacy.py               Pure reconstructed final-score rule
  persistence/                    Backend credentials and Supabase operations
research/                         Training and historical experiments
data/baseline/                   Frozen reference inputs/outputs
```

The package is installed by `uv sync --frozen`. Python can then import `safetrip` without depending on the caller's working directory. Paths resolve against the checkout when discoverable; set `SAFETRIP_PROJECT_ROOT` when deploying a wheel without the source checkout. Model files and data are deliberately not bundled into the wheel.

Importing runtime modules or legacy writer wrappers does not load credentials, create database clients, import the ML stack, fetch advisories, or publish data. Third-party libraries load inside the operations that need them. `--help` works without those libraries. CI installs the actual package with `--no-deps` and exercises the lightweight tests.

The build backend is pinned in `pyproject.toml`. uv 0.12.23 or newer is required. Updating the lockfile with the standalone uv version rewrote lock-format metadata but changed no dependency versions. If an older Conda-installed uv still takes precedence in your shell, use the Homebrew executable or update PATH as described in the repository guide.

## Try the commands safely

From the project root, use a fresh output path for each run:

```sh
uv sync --frozen
uv run --frozen safetrip --help
uv run --frozen safetrip ingest \
  --input tests/fixtures/advisories.xml \
  --output .local/demo/advisories.json
uv run --frozen safetrip score \
  --input .local/demo/advisories.json \
  --output .local/demo/bert-scores.json
```

`score` needs the verified local checkpoint at `results/checkpoint-189`, or `--model-path`. These examples use synthetic inputs and make no database calls. Outputs are created exclusively; an existing file causes failure instead of being overwritten.

`refresh` combines those two stages:

```sh
uv run --frozen safetrip refresh \
  --input tests/fixtures/advisories.xml \
  --output .local/demo/refresh.json
```

Its artifact contains `advisories` and `bert_scores`. Omitting `--input` from `ingest` or `refresh` fetches the configured-in-code State Department feed; it does not start retraining. The parser first uses the preserved manual overrides and country-code mapping. An optional `--iso-csv` / `SAFETRIP_ISO_CSV` supplies the historical name fallback. Missing mappings or empty input now fail rather than silently publishing an incomplete result. The missing historical CSV is therefore needed only for records that cannot be resolved by existing codes/overrides.

Cleaning rules, label IDs, tokenization length, model bytes, baseline datasets, and final-score mathematics were preserved. Inference explicitly runs on CPU. Duplicate feed entries retain the historical last-entry-per-ISO3 rule. Improving that rule and evaluating cleaner changes remain Phase 4 work.

## Publication is explicit and still interim

Appending `--write` publishes to the configured Supabase project with the existing backend-only credentials. Do not append it to the synthetic examples above. Local output is saved before publication; the existence of a JSON artifact is not evidence of successful database publication.

| Command | Publication with `--write` |
| --- | --- |
| `ingest` | Upserts `travel_advisories` |
| `score` | Upserts `bert_scores` after checking country identifiers |
| `refresh` | Both of the above, sequentially |
| `seed-countries` | Upserts ISO3/ISO2/name rows, without deliberately clearing continent/flag values |
| `import-clusters` | Upserts the selected CSV's raw cluster IDs and feature scores |

**These commands do not update the displayed final `scores` table.** Refresh currently means refreshing intermediate advisory/classification data. Final-score publication was not a working scripted part of the historical pipeline; adding it transactionally is Phase 4 work. The CLI does not silently introduce a new production score recalculation.

Supabase publication is not atomic across tables or batches. A failure can leave partial writes. Retries, overlap prevention, run records, complete-result transactions, and artifact/model promotion remain later milestones. The historical `modify_clustering.py` now requires `--write` and is import-safe, but remains non-idempotent and unsuitable for routine refreshes.

The legacy `db/scripts/populate_*.py` and `score_advisories.py` are compatibility command wrappers. They now require `--output` and explicit `--write` for publication. Update any external manual invocation accordingly; no external scheduler was configured or modified here. Security backup/check utilities remain under `db/scripts/` and require the installed package when using the shared writer helper.

## Typed server queries

`frontend/src/lib/server/queries.ts` owns the site's database reads. `server-only` prevents browser components from importing this module. It uses the public read credential, never a service-role credential. Row types match the backed-up application schema; these TypeScript declarations are not runtime validation or generated migrations.

- A successful lookup with no country produces a not-found page.
- Missing optional culture or score data remains optional.
- Failed queries produce a temporary-unavailability response instead of pretending the country or score does not exist.
- The APIs return HTTP 503 on database failure. Search/map show an error message; country pages use a retryable error boundary.
- A null final score is not formatted or displayed as a numeric score.

The database layer remains Supabase for now. Direct PostgreSQL access and distinct database roles belong to Phase 3.

## Verification and exit status

Local checks passed: 22 Python tests including configuration/import/command boundaries, four frontend query tests, clean dependency install, production audit, TypeScript, lint, and Next.js build. Existing three image-optimization warnings and the documented development-only dependency advisory remain.

The baseline still matches 212 scores, 168 cluster assignments, and two checkpoint predictions. All 18 relocated data/chart files were byte-identical during the preceding research move. Fixture ingest/score/refresh completed without database access. Local Chromium smoke checks cover home/map/search behavior and simulated API outages; live database reads and Vercel deployment still require preview verification.

Phase 2 implementation is ready for review. Its deployment exit criterion is complete only after the combined changes pass GitHub CI and the Vercel preview's search, map, and country pages are checked. No production writes, retraining, or deployment occurred during this work.

Next: Phase 3 adds Docker, disposable local PostgreSQL, migrations, and scoped database access. The frontend redesign can follow those foundations.

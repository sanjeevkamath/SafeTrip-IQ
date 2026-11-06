# Repository guide

Production and research share versioned code and regression fixtures, but the weekly worker does not train or load ML models.

| Location | Responsibility |
| --- | --- |
| `frontend/` | Deployed Next.js website; preserve this Vercel root |
| `pipeline/src/safetrip/ingestion/` | US/UK capture, normalization, ISO3 mappings and preserved source text |
| `pipeline/src/safetrip/scoring/official.py` | Versioned official-US-plus-clustering formula |
| `pipeline/src/safetrip/persistence/` | Scoped transactions, immutable history and run ledger |
| `db/hosted/` | Reviewed additive SQL for hosted Supabase; apply manually in order |
| `db/migrations/`, `db/local/` | Local Alembic chain, restricted development roles and synthetic seeds |
| `db/scripts/hosted_advisories.py`, `hosted_reader.py` | Scoped hosted ingestion/reader setup and checks |
| `db/scripts/preview_official_scores.py`, `publish_official_scores.py` | Read-only preview and explicit atomic score publication |
| `db/security/restore_official_scores.sql` | Owner-reviewed incident restoration, rollback by default |
| `.github/workflows/` | CI, worker-image publishing, weekly advisory refresh and daily public health monitoring |
| `scripts/` | Operational checks, local setup, CI gates, historical baseline verification and optional AWS benchmarking |
| `research/scripts/` | BERT/linear evaluation, label audits, dataset preparation and advisory NLP pilots |
| `research/bert/`, `research/clustering/`, `research/advisory_nlp/` | Experimental training, historical preparation and pilot evidence extraction |
| `research/legacy_data_preparation/` | Archived original scrapers; unsupported for production |
| `data/baseline/` | Frozen regression inputs; do not clean/retrain them in place |
| `tests/`, `db/integration/`, `frontend/tests/` | Unit, real PostgreSQL, rendering, query and browser checks |
| `.local/` | Ignored credentials, captures, checkpoints for experiments, artifacts and tooling; never commit |

## Supported paths

The deployed refresh uses only the `advisory-refresh` uv dependency group: HTTP, dotenv, SQLAlchemy and psycopg. The full default environment retains ML dependencies for baseline reproduction and historical worker/benchmark paths. `requirements.txt` is a compatibility export; dependency changes belong in `pyproject.toml` and `uv.lock`. Conda exports are retired.

The four old `db/scripts/populate_*.py`/`score_advisories.py` wrappers and `safetrip score`/`refresh` retain historical BERT behavior for reproducibility. They are not the V2 production workflow. Do not chain them into the scheduled refresh or use them as connectivity tests. The unsafe non-idempotent `modify_clustering.py` remapper has been removed; its source remains in Git history. No clustering tiers were changed by cleanup.

Fifteen audit/evaluation/experiment entry points moved from `scripts/` to `research/scripts/`. Invoke them from the repository root as `python -m research.scripts.<name>`; imports, root path resolution, tests and current experiment instructions were updated. Historical script limitations remain documented in [research](../research/README.md).

`research/clustering/data/clustering_results.csv` was byte-identical to `clustering_output.csv` and had no tracked code consumers; the duplicate was removed. The retained exploratory output differs from the verified `data/baseline/clustering/clusters.csv`. No dataset was deleted based on a similar filename. Frozen CSV hashes and the 212-score historical regression remain unchanged.

The local development seed has three synthetic countries. Hosted production had 250 catalogue destinations, 215 numeric scores and 35 missing scores at the November 2026 rollout. Missing means unavailable data, not safety. Historical baselines contain 212 rows and 168 clustering assignments; those counts describe different snapshots.

Use [operations](operations.md) for schedules, alerts and recovery, [official scoring](official-us-scoring.md) for the formula/publication contract, and [the documentation index](README.md) to distinguish current guides from historical checkpoints. The former repository inventory is preserved under [archive](archive/repository-guide-pre-v2.md).

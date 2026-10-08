# Repository guide

This inventory describes the current repository before moving files into a Python package. “Baseline” means a preserved reference for refactoring, not a claim that a model or dataset is scientifically correct.

## Python environment

Use uv from the repository root:

```sh
uv sync --frozen
uv run --frozen python -m scripts.verify_baseline
```

`pyproject.toml` declares direct dependencies and optional extras; `uv.lock` fixes the resolved dependencies; `.python-version` selects Python 3.11; `.venv` holds the local installation. `requirements.txt` is a compatibility export, not a second manually maintained dependency list. The frontend separately uses npm and its package lock.

For research dependencies, use `uv sync --frozen --extra research`, then include `--extra research` when using `uv run`. Database audit utilities use the `audit` extra. Neither extra makes historical scripts safe to execute or guarantees that missing research inputs are available.

The project uses uv-managed Python, independent of Conda. `python-preference = "only-managed"` in `pyproject.toml` prevents fallback to a Conda/system interpreter when selecting Python. The maintainer's `.venv` has been recreated with standalone CPython 3.11.17. Dependencies remain at their existing locked versions.

On macOS, install standalone uv with `brew install uv`, then run `uv python install 3.11` and `uv sync --frozen`. If your shell still resolves uv inside a Conda installation, run `conda deactivate` (repeat for stacked environments) and use `/opt/homebrew/bin/uv` on Apple Silicon. Check `command -v uv`. No changes to global shell startup files are required by this project.

To confirm the project's interpreter, run:

```sh
uv run --frozen python -c 'import sys; print(sys.executable); print(sys.base_prefix)'
```

The executable should be in `.venv`, and the base prefix should be in uv's managed Python directory. Select `.venv/bin/python` as the interpreter in your editor. If migrating an older checkout, move its Conda-backed `.venv` aside before syncing; changing configuration alone is not a substitute for verifying an existing environment.

Database command-line utilities are separate from Python dependencies. On macOS, `brew install postgresql@17` supplies `pg_dump`, `psql`, and local test-server binaries. For a schema backup, pass `--pg-dump "$(brew --prefix postgresql@17)/bin/pg_dump"` to the existing backup script, using `uv run --frozen --extra audit python`. Installing these tools does not require enabling a background database service. The old Conda-based security tooling is no longer needed; private snapshots, certificates, and the isolated test database remain under `.local/`.

See [uv's Python management documentation](https://docs.astral.sh/uv/concepts/python-versions/) for managed interpreter installation on other platforms.

CI installs the runtime package without dependencies and runs lightweight checks. It does not install the full ML environment or load model weights.

### Standalone environment verification (2026-10-08)

- Installed standalone Homebrew uv and uv-managed CPython 3.11.17; rebuilt `.venv` with all extras from the unchanged lockfile.
- Verified core, research, and audit package imports. No retraining was performed.
- With Conda removed from PATH and its selection variables unset, passed the full local CI script and the extended baseline: 212 final scores, two checkpoint predictions, and 168 cluster assignments.
- Confirmed Homebrew `pg_dump` and `psql` version 17.11. No production database connection or background database service was needed.
- Removed `.local/previous-conda-venv`, `.local/security-tools`, and `.local/conda-cache` after verification. Retained private exports, certificates, and isolated database files. System-wide Conda remains untouched for other projects.
- Frontend installation reported 21 npm audit findings, including a critical finding for the direct `next` dependency. The subsequent [dependency patch](dependency-security.md) resolved the production findings and documents the remaining development-tool advisory separately.

## Code responsibilities

| Location | Current responsibility |
| --- | --- |
| `frontend/` | Deployed Next.js application; keep this path stable for Vercel |
| `pipeline/src/safetrip/` | Installable runtime package: ingestion, inference, scoring, persistence, orchestration, and CLI |
| `db/scripts/score_advisories.py` | Compatibility wrapper for `safetrip score`; local artifact by default |
| `db/scripts/populate_*.py` | Import-safe compatibility commands; publication requires `--write` |
| `db/scripts/modify_clustering.py` | Historical one-time tier remapping; rerunning changes already mapped values |
| `db/scripts/supabase_writer.py` | Backend credential validation and client creation |
| `db/scripts/backup_schema.py`, `capture_data_baseline.py`, `check_writer_connection.py` | Security audit and read-only snapshot/connection utilities |
| `db/security/` | Reviewed Phase 0 SQL and permission verification |
| `research/bert/` | Explicit `train.py` experiment and historical advisory preparation |
| `research/clustering/` | Explicit `fit.py` experiment plus preserved historical preprocessing and charts |
| `research/legacy_data_preparation/` | Historical data preparation; preserve until dependencies and provenance are traced |
| `scripts/`, `tests/`, `db/tests/` | Developer checks, score fixtures, credential tests, and isolated permission testing |

Runtime writers now have explicit commands and do no work on import. Historical research scripts retain their separately documented limitations.

## Data and model inventory

| Path | Status |
| --- | --- |
| `tests/fixtures/legacy_scores.json` | Authoritative 212-row regression snapshot for the recovered score formula |
| `tests/fixtures/bert_predictions.json` | Two captured behavioral predictions, not accuracy labels |
| `docs/baseline/artifacts.json` | Hash manifest identifying the preserved model and datasets |
| `data/baseline/clustering/features.csv` | Frozen feature input used by the clustering reproduction check |
| `data/baseline/clustering/clusters.csv` | Verified 168-country baseline output; raw cluster IDs, not final risk tiers |
| `research/clustering/data/clustering_output.csv`, `clustering_results.csv` | Byte-identical to each other, but different from the verified output above; retained pending provenance review |
| `research/clustering/data/old_data/` | Historical intermediate files; includes an empty `training.csv`; retained for the data review |
| `data/baseline/bert/train.csv`, `test.csv` | Preserved training/test inputs with known text overlap; evaluation needs repair |
| `research/bert/wayback/` | Historical source preparation and multiple dataset variants; no deletion based on similar names |
| `results/checkpoint-189/` | Ignored local model artifact, verified by manifest; requires separate distribution |
| `.local/` | Ignored private audit exports, certificates, and local tooling; never publish this directory |

## First cleanup decisions

- Untrack `.idea/` and `.DS_Store` while retaining the local files. Existing ignore rules prevent reintroduction.
- Remove four `envs/*.yml` exports and `safe_trip_env.yml`. The imports in the current Python sources are covered by the declared core/research/audit dependencies or their locked dependencies. Old exports contain differing Torch/Transformers/NumPy versions, machine prefixes, and native Conda build details; they are historical snapshots, not interchangeable setup instructions. CUDA/Triton packages and torchvision/torchaudio are not used by the current source imports and are intentionally absent from the CPU inference setup. Native PostgreSQL tools used for security backups are separate local tooling.
- Preserve the removed exports in Git history. Their removal does not uninstall any environment or certify that the original training run is reproducible.
- Remove empty `backend/.gitkeep`, `models/BERT/best/.gitkeep`, `db/.gitkeep`, and empty `db/scripts/update_advisories.py`. Implementations will introduce meaningful paths when needed.
- Remove the unused Next.js starter SVGs after checking tracked source references.
- Remove the joke block from the clustering writer without changing its database operations.

No dataset content, checkpoint, scoring rule, deployment root, or database permission changed in the initial cleanup.

## Research separation

Model development now lives in `research/`; the four verified CSVs live in `data/baseline/` with unchanged hashes. The baseline verifier, legacy clustering writer default, environment example, and manifest use the new paths. If a private environment explicitly sets `SAFETRIP_CLUSTERING_CSV` to the former default path, update it to `data/baseline/clustering/clusters.csv`.

See `research/README.md` for explicit model entry points and the limits of the historical scripts. New training and clustering experiment outputs are isolated under timestamped `.local/research/` directories. Only import/help behavior and the historical baseline were verified; a new BERT training run was not performed.

The runtime package extraction and typed server query changes are implemented. See [Phase 2](phase-2-runtime.md) for commands, tests, and remaining deployment verification.

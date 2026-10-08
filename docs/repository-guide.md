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

The maintainer's existing `.venv` was created with a Python interpreter supplied by Conda. uv manages the packages in that isolated environment; Conda still supplies its base interpreter. Do not remove that Conda installation until `.venv` has been recreated with an independently installed Python 3.11 interpreter.

Basic CI tests use Python's standard library, so CI currently does not install the full uv environment or load model weights.

## Code responsibilities

| Location | Current responsibility |
| --- | --- |
| `frontend/` | Deployed Next.js application; keep this path stable for Vercel |
| `pipeline/scoring.py` | Pure reconstructed final-score rule, currently used for offline verification |
| `db/scripts/score_advisories.py` | Local checkpoint loading and advisory inference; main command writes to the configured database |
| `db/scripts/populate_*.py` | Legacy ingestion and publication scripts; some perform writes on import |
| `db/scripts/modify_clustering.py` | Historical one-time tier remapping; rerunning changes already mapped values |
| `db/scripts/supabase_writer.py` | Backend credential validation and client creation |
| `db/scripts/backup_schema.py`, `capture_data_baseline.py`, `check_writer_connection.py` | Security audit and read-only snapshot/connection utilities |
| `db/security/` | Reviewed Phase 0 SQL and permission verification |
| `pipeline/BERT/` | Training and historical advisory preparation; candidate for `research/` |
| `pipeline/clustering/` | Feature preparation, model fitting, visualizations and datasets; candidate for separation into research and baseline inputs |
| `pipeline/scrapers/` | Historical data preparation; preserve until dependencies and provenance are traced |
| `scripts/`, `tests/`, `db/tests/` | Developer checks, score fixtures, credential tests, and isolated permission testing |

Do not run legacy writer scripts as a cleanup verification step. The next extraction will give runtime code explicit entry points and remove import-time work.

## Data and model inventory

| Path | Status |
| --- | --- |
| `tests/fixtures/legacy_scores.json` | Authoritative 212-row regression snapshot for the recovered score formula |
| `tests/fixtures/bert_predictions.json` | Two captured behavioral predictions, not accuracy labels |
| `docs/baseline/artifacts.json` | Hash manifest identifying the preserved model and datasets |
| `pipeline/clustering/data/clustering_ready.csv` | Frozen feature input used by the clustering reproduction check |
| `pipeline/clustering/output/clustering_output.csv` | Verified 168-country baseline output; raw cluster IDs, not final risk tiers |
| `pipeline/clustering/data/clustering_output.csv`, `clustering_results.csv` | Byte-identical to each other, but different from the verified output above; retained pending provenance review |
| `pipeline/clustering/data/old_data/` | Historical intermediate files; includes an empty `training.csv`; retained for the data review |
| `pipeline/BERT/train.csv`, `test.csv` | Preserved training/test inputs with known text overlap; evaluation needs repair |
| `pipeline/BERT/wayback/` | Historical source preparation and multiple dataset variants; no deletion based on similar names |
| `results/checkpoint-189/` | Ignored local model artifact, verified by manifest; requires separate distribution |
| `.local/` | Ignored private audit exports, certificates, and local tooling; never publish this directory |

## First cleanup decisions

- Untrack `.idea/` and `.DS_Store` while retaining the local files. Existing ignore rules prevent reintroduction.
- Remove four `envs/*.yml` exports and `safe_trip_env.yml`. The imports in the current Python sources are covered by the declared core/research/audit dependencies or their locked dependencies. Old exports contain differing Torch/Transformers/NumPy versions, machine prefixes, and native Conda build details; they are historical snapshots, not interchangeable setup instructions. CUDA/Triton packages and torchvision/torchaudio are not used by the current source imports and are intentionally absent from the CPU inference setup. Native PostgreSQL tools used for security backups are separate local tooling.
- Preserve the removed exports in Git history. Their removal does not uninstall any environment or certify that the original training run is reproducible.
- Remove empty `backend/.gitkeep`, `models/BERT/best/.gitkeep`, `db/.gitkeep`, and empty `db/scripts/update_advisories.py`. Implementations will introduce meaningful paths when needed.
- Remove the unused Next.js starter SVGs after checking tracked source references.
- Remove the joke block from the clustering writer without changing its database operations.

No dataset, checkpoint, scoring rule, deployment root, or database permission is changed by this cleanup. The next pass separates research from runtime code in small changes protected by CI.

# SafeTrip-IQ

ML-based travel advisory project for Gator AI. A Next.js website reads country information and stored safety scores from Supabase PostgreSQL. Python scripts prepare advisory classifications and country clusters.

The project is being made reproducible before introducing containers and AWS deployment. See the [production roadmap](docs/production-roadmap.md), [security evidence](docs/phase-0-security.md), and [baseline walkthrough](docs/phase-1-baseline.md).

The [repository guide](docs/repository-guide.md) explains the uv environment, current script responsibilities, and which datasets form the verified baseline.

Model experiments are in [research](research/README.md); frozen reference datasets are in [data/baseline](data/baseline/README.md). The installable runtime package is in `pipeline/src/safetrip/`; `db/scripts/` retains compatibility commands and audit utilities. See the [Phase 2 walkthrough](docs/phase-2-runtime.md).

## Reproduce the scoring baseline

From the repository root, without credentials or a database:

```sh
uv sync --frozen
uv run --frozen python -m scripts.verify_baseline
uv run --frozen python -m unittest discover -s tests -v
```

These checks reproduce 212 captured scores. They verify historical behavior, not the accuracy of travel advice.

For the Python pipeline, install standalone uv (`brew install uv` on macOS). uv supplies Python 3.11; Conda is not required:

```sh
uv python install 3.11
uv sync --frozen
uv run --frozen python -m scripts.verify_baseline --with-clustering
```

The lock targets Apple Silicon macOS and Linux x86_64, using CPU-only PyTorch on Linux. Model verification additionally requires the six local checkpoint files listed in `docs/baseline/artifacts.json`; these are not distributed in Git:

```sh
uv run --frozen python -m scripts.verify_baseline --with-model
```

## Local PostgreSQL (Phase 3 in progress)

With Docker Desktop running, start the development database from this directory:

```sh
bash scripts/setup_local_db.sh
```

This starts PostgreSQL, provisions restricted roles, applies Alembic migrations, and upserts three development countries. Run `bash scripts/check_database.sh` to verify migrations, seed repeatability, and permissions. See the [local Postgres walkthrough](docs/phase-3-local-postgres.md) for SQL access, ports, persistent storage, and shutdown. Run `cd frontend && npm run dev:local` to use it from the website. The worker selects it through `bash scripts/worker_local.sh`; production defaults remain Supabase during this transition.

Container commands and the optional model mount are documented in the same walkthrough. `docker compose build web migrate worker` builds the non-root website, migration, and CPU worker images; `docker compose up -d --wait web` serves the containerized site on port 3001. `bash scripts/check_containers.sh` runs the local container smoke checks.

## Website

Configure `frontend/.env.local` with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` for your Supabase project, then:

```sh
cd frontend
npm ci
npm run dev
```

Use `npm run build` to check the production build. The public client requires read access to `countries`, `culture`, and `scores`. Backend credentials belong only in the ignored root `.env`; `.env.example` documents the settings. Never put a service-role credential in a `NEXT_PUBLIC_` variable.

The `safetrip ingest`, `score`, and `refresh` commands create local artifacts by default; publication requires `--write`. Those commands default to Supabase when publishing. Use `bash scripts/worker_local.sh` with the same arguments to explicitly target Docker Postgres. The local Postgres walkthrough includes a synthetic fixture example; final scores are not yet recalculated by refresh.

## Continuous integration

GitHub Actions runs `.github/workflows/ci.yml` for pull requests, pushes to `main`, and manual dispatch. Independent jobs check the website (Node 22), lightweight Python package tests (Python 3.11), and a disposable Docker PostgreSQL database. These jobs use no production secrets, model downloads, or retraining.

The frontend job also blocks high/critical production dependency advisories. See the [dependency security record](docs/dependency-security.md) for the patch and remaining development-tool advisory.

Run equivalent checks locally from the project root:

```sh
bash scripts/check_ci.sh
```

Use Node 22 and standalone uv. The script installs the runtime package without ML dependencies into disposable `.local/ci-python` using uv-managed Python 3.11, reinstalls frontend dependencies from the lockfile, and uses dummy Supabase settings. It stops at the first failed command. This runs the commands locally; GitHub runs them on fresh Linux runners using its own Python setup action.

After committing and pushing the workflow **and its referenced scripts, fixtures, and baseline manifest**, a push to `main` triggers CI automatically. Once the workflow is on the default branch, manually trigger it using an authenticated GitHub CLI:

```sh
gh workflow run ci.yml --ref main
gh run list --workflow ci.yml --limit 5
```

Alternatively, use GitHub → Actions → CI → Run workflow. Passing CI is verification only; this workflow does not deploy or publish scores.

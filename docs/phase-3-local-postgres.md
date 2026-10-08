# Phase 3: local PostgreSQL, migrations, and roles

Run these commands from the repository root with Docker Desktop running:

```sh
bash scripts/setup_local_db.sh
docker compose ps
docker compose exec db psql -U safetrip_admin -d safetrip
```

At the SQL prompt, try:

```sql
SELECT current_database(), current_user, version();
```

Use `\q` to leave psql. No host installation of psql is needed: `exec` runs the copy inside the database container.

## What Compose starts

- **Image:** `postgres:17.11-bookworm` is the official PostgreSQL software/environment template, pinned to a patch version. It supports this Mac's ARM architecture. The tag can receive rebuilt base-image layers; this is not an immutable digest pin.
- **Container:** the running instance of that image. Compose manages it as the service `db`.
- **Port:** `127.0.0.1:55432:5432` forwards this Mac's port 55432 to PostgreSQL's port 5432 inside the container. Binding to 127.0.0.1 keeps it off the local network. Future containers in this Compose project connect to `db:5432`; host processes connect to `127.0.0.1:55432`.
- **Volume:** `postgres_data` stores database files outside the container's writable layer. Recreating the container keeps the data. Docker manages the files; they are not committed to Git.
- **Health check:** `pg_isready` checks whether PostgreSQL accepts connections. `--wait` waits for a healthy container. This does not check application migrations or permission correctness.

The database is named `safetrip`. The local administrative login is `safetrip_admin` / `safetrip_local_only`. These deliberately public development credentials must never be reused on a hosted database. The image creates this bootstrap account as a database superuser; it is used only for local role provisioning and disposable test databases.

Compose passes only the three explicitly listed variables into Postgres. It does not pass the repository's Supabase credentials into the container. The setup script uses fixed local connections and does not load `.env`. It copies no live production data. Development seeds include three previously captured score fixtures. The local application can now connect with explicit Postgres configuration; the deployed Vercel/Supabase configuration is unchanged.

## Schema changes are code

`alembic.ini` points to `db/migrations`. Revision `0001` recreates the six application tables from the inspected schema backup, preserving types, nullable columns, primary keys, the countries ISO2 index, and the three existing foreign keys. It does not introduce new score bounds or foreign keys on `scores`/`travel_advisories`; those changes need explicit later migrations and data validation. Supabase-managed schemas, extensions, API roles, and grants are not copied.

Alembic records applied revisions in `alembic_version`. Running `upgrade head` again does not rerun an applied migration. Future schema changes get a new revision with an `upgrade()` and `downgrade()`; do not edit a migration once deployed. This first revision is for an empty database, not an existing Supabase schema. Production adoption requires a separate schema comparison and baseline procedure; do not apply or stamp it on production yet.

`scripts/setup_local_db.sh` performs three separate operations:

1. The local admin runs `db/local/bootstrap.sql` to provision roles/schema privileges.
2. The migration account runs Alembic to create tables and their RLS policies/grants.
3. The writer runs `db/local/seed.sql` to upsert repeatable fixtures in one transaction.

Alembic, SQLAlchemy, and psycopg are pinned in the `database` dependency group. Scripts use `.local/database-venv` and install only that group, avoiding a model/PyTorch installation and leaving the main `.venv` alone. SQLAlchemy supplies the migration connection; psycopg is the PostgreSQL driver. The worker now has a SQLAlchemy adapter and the website has a server-only node-postgres adapter.

## Separate responsibilities

| Local login | Local password | Access |
| --- | --- | --- |
| `safetrip_migrator` | `migrator_local_only` | Owns the application schema/tables and runs DDL; no superuser or role-creation privilege |
| `safetrip_reader` | `reader_local_only` | SELECT on countries, culture, scores only |
| `safetrip_writer` | `writer_local_only` | SELECT/INSERT/UPDATE/DELETE on the six application tables; no TRUNCATE, DDL, or role escalation |

Both application roles are non-owners without BYPASSRLS. Each allowed operation needs both a table grant and an applicable RLS policy. The writer can operate across all rows in these six tables; this is a table-scoped batch writer, not per-user tenant isolation. The migration owner normally bypasses RLS through ownership and must not be used as an application credential. Future tables receive no automatic application grants; future functions receive no PUBLIC execution by default.

The bootstrap SQL contains fixed development passwords and is local-only. Hosted role provisioning will supply separate secrets. Existing local role passwords are not reset by rerunning bootstrap.

Try the reader with password authentication:

```sh
docker compose exec -e PGPASSWORD=reader_local_only db \
  psql -h 127.0.0.1 -U safetrip_reader -d safetrip
```

```sql
SELECT * FROM scores;
UPDATE scores SET safe_trip_score = 0 WHERE false;
```

The SELECT succeeds; the UPDATE receives `permission denied`, even though its predicate would affect no rows. Use `\q` to exit.

## Development seeds and verification

Canada, Japan, and the United States use scores from the frozen baseline: 10, 10, and 6 respectively. These are historical regression examples, not current travel guidance. Text is synthetic, timestamps are fixed, and the US lacks culture/BERT data to exercise optional-data behavior. Repeated setup upserts these fixtures, intentionally restoring their seeded fields; it does not remove unrelated local rows.

```sh
bash scripts/check_database.sh
```

This reruns setup and tests the three captured scores, missing optional data, denied reader mutations/internal reads, worker CRUD, prohibited DDL/TRUNCATE/escalation, non-owner roles/RLS, an existing foreign key, and repeatable seeds. Upgrade/no-op upgrade/downgrade/re-upgrade run in a uniquely named disposable database which is dropped in cleanup. Writer probes and seed-repeatability checks roll back. Run against the dedicated development database: the exact seed-count assertion assumes no additional country rows.

GitHub CI runs the same checks in a separate database job and removes its volume afterward. The existing `check_ci.sh` remains the frontend/lightweight Python check; run `check_database.sh` for this integration suite. No tests connect to Supabase.

## Everyday commands

```sh
# Start (or reuse) the database, waiting for readiness
docker compose up -d --wait db

# Inspect status and recent logs
docker compose ps
docker compose logs --tail=50 db

# Stop/remove the container and network, preserving the database volume
docker compose down
```

`docker compose down --volumes` also deletes this project's local database volume and its data. Use that only when intentionally resetting this development database. Changing the bootstrap credentials in YAML does not change an existing database's password: image initialization happens only on an empty data directory.

## Remaining Phase 3 work

Local application connectivity is implemented. Next we build the website and worker Docker images. Final-score publication, full refresh reliability, hosted TLS/pooling configuration, and production adoption remain separate steps.

References: [official Postgres image](https://hub.docker.com/_/postgres), [Compose services](https://docs.docker.com/reference/compose-file/services/), [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [PostgreSQL privileges](https://www.postgresql.org/docs/17/ddl-priv.html).


## Run the application against local Postgres

From the project root:

```sh
bash scripts/setup_local_db.sh
cd frontend
npm ci
npm run dev:local
```

Open http://localhost:3000 and search for Canada, Japan, or United States. Only these seeded countries have local data. `dev:local` sets `SAFETRIP_DB_BACKEND=postgres` and a server-only `SAFETRIP_DATABASE_URL` using `safetrip_reader`. It overrides the backend for this process without editing existing environment files. The browser calls Next.js; only Next.js connects to Postgres. The database password is never a `NEXT_PUBLIC_` variable.

The Postgres adapter uses parameterized SQL, deterministic search ordering, literal substring matching (SQL wildcards are escaped), and a reusable pool capped at two connections per process. Connection and statement timeouts are bounded. Missing optional rows stay null; failures become generic unavailable errors. No raw driver exception/URL is logged. The current URL validation requires the literal `safetrip_reader` username.

In another terminal at the project root, run the worker using a fresh output filename:

```sh
bash scripts/worker_local.sh ingest \
  --input tests/fixtures/advisories.xml \
  --output .local/demo/postgres-advisories.json --write
```

This wrapper selects Postgres with `safetrip_writer` explicitly, even if `.env` contains Supabase credentials. Without `--write`, it creates only the output artifact. For real checkpoint inference, use `refresh` instead of `ingest`; the verified local model must exist. These fixture texts are synthetic development data, not live travel advice.

Postgres publication uses one SQLAlchemy transaction per command and parameterized upserts with a table/column allowlist. A failed `refresh` rolls back both its advisory and BERT changes. Only supplied columns are updated, so country catalog imports preserve existing continent/flag values. The one-shot writer uses NullPool, a connection timeout, and a statement timeout; it disposes its engine on exit. Its URL requires the literal `safetrip_writer` username and `postgresql+psycopg` driver.

**Final `scores` rows are still unchanged by worker refresh.** Transactional intermediate writes do not yet implement final-score publication, retries, run tracking, or overlap prevention. The output JSON is saved before publication and remains on failure; it is not proof of committed database data.

## Controlled backend transition

Both runtimes retain a Supabase adapter, selected when `SAFETRIP_DB_BACKEND` is unset or `supabase`. This preserves the existing deployment while local Postgres is tested. Setting `postgres` requires its separate database URL. Invalid configuration or connection failure never triggers automatic fallback to Supabase. Historical Supabase maintenance scripts still use their original credentials; use the local worker wrapper for the new commands.

Do not set the worker URL in the website. Do not change Vercel configuration yet. Hosted deployment needs dedicated role provisioning, verified TLS, pooler-compatible URLs and connection limits, schema comparison, and preview validation. Local plain TCP on loopback is not the production connection configuration.

## Test the application adapters

```sh
# Ten Python database tests, including real CLI publication and rollback
bash scripts/check_database.sh

# Three frontend integration tests using actual SQL and the reader account
cd frontend
npm run test:postgres
```

The database CI job runs both suites. The existing frontend suite also preserves Supabase error-handling coverage. Python lightweight tests verify backend selection and import safety without database/ML dependencies. Database tests restore committed fixture changes after application-publication checks; transaction failure probes leave no rows behind.

## Container checkpoint

The repository now contains separate production-style images:

- `frontend/Dockerfile` builds Next.js with standalone output, then copies only the runtime bundle into a non-root Node image.
- `pipeline/Dockerfile` has a small migration target and a worker target. The worker installs only the `worker` dependency group, runs as UID 10001, and expects the checkpoint to be mounted separately.
- `.dockerignore` keeps `.env`, `.local`, `results`, `node_modules`, and the rest of the research tree out of build contexts.
- `compose.yaml` starts bootstrap roles, migrations, seeds, the website on `http://localhost:3001`, and the database. The worker is an on-demand `jobs` profile.
- `compose.model.yaml` is an optional override that mounts `results/checkpoint-189` read-only at `/models/checkpoint-189`.

Build and start the website from the project root:

```sh
docker compose build web migrate worker
docker compose up -d --wait web
open http://localhost:3001
```

The first build downloads the Node and Python base images and the CPU PyTorch wheel. On Apple Silicon, the migration and worker use `linux/amd64` because the current locked Linux ML dependencies target x86_64; Docker Desktop emulates that architecture. The database and Node image use the host's normal Docker architecture. This is a local compatibility choice; a later AWS image can be built natively for its selected ECS architecture.

Run an on-demand worker without the checkpoint:

```sh
docker compose run --rm --no-deps worker --help
docker compose run --rm --no-deps worker ingest \\
  --input /app/fixtures/advisories.xml \\
  --output /output/container-advisories.json --write
```

For BERT inference, add the model override, create an advisory artifact in the shared output volume, then score it:

```sh
docker compose -f compose.yaml -f compose.model.yaml run --rm --no-deps worker \\
  ingest --input /app/fixtures/advisories.xml \\
  --output /output/container-advisories.json
docker compose -f compose.yaml -f compose.model.yaml run --rm --no-deps worker \\
  score --input /output/container-advisories.json \\
  --output /output/container-bert.json
```

The current fixture is XML, so `refresh` needs an intermediate ingest artifact or a mounted input file. The model manifest is copied into the image; `SAFETRIP_MODEL_MANIFEST` causes every mounted model file's size and SHA-256 to be checked before loading. A tampered or incomplete mount fails before inference. The model is deliberately not copied into the image because it is a local ignored artifact and would make every code image roughly 438 MB larger.

Run the disposable container checks:

```sh
bash scripts/check_containers.sh
```

This builds all targets, checks non-root/CPU-only worker behavior, confirms the web image reads the seeded rows, runs a no-model worker command, and publishes a synthetic advisory through the writer role. It does not use Supabase or copy production data. The script leaves the web service at `http://localhost:3001`; use `docker compose down` afterward. The complete Docker build requires a running Docker daemon and registry access; CI runs the same check on Linux.

Local verification completed: 10 Python database integration tests, 3 frontend Postgres integration tests, 23 lightweight Python/credential tests, 4 Supabase query tests, production dependency audit, TypeScript, lint, and production build. The existing three image warnings and development-only dependency advisory remain. A browser smoke check against the built server and real local database verified search, map data, Canada/US pages, displayed scores, and a missing-country 404. Map geometry was stubbed and external browser requests blocked. A real checkpoint refresh on the two synthetic advisories matched the committed local BERT rows; the deterministic seeds were restored afterward. Hosted deployment has not been tested or changed.

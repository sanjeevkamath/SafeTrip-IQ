# SafeTrip IQ website

Next.js/TypeScript frontend deployed on Vercel from this directory. For the project architecture, scoring formula and setup, start with the [root README](../README.md).

## Local development

Use Node.js 22. From the repository root, start the fixture database with `bash scripts/setup_local_db.sh`. Then, from this directory:

```sh
npm ci
npm run dev:local
```

Open `http://localhost:3000`. The three-country synthetic seed requires no hosted credentials. `npm run dev:full` is only for the separately imported local `safetrip_full` dataset. Plain `npm run dev` uses the configured Supabase backend; use the local command for a fresh clone.

## Production data

Map/search/catalogue reads use public read-only Supabase access. Official advice and current score methodology use the dedicated server-only PostgreSQL reader. Country scores use the versioned official-US-plus-clustering formula; UK warnings and regional coverage remain separate. Missing scores are unavailable data, not low risk.

Keep privileged credentials out of `NEXT_PUBLIC_*`. The website does not receive ingestion or score-publisher credentials. [Hosted setup](../docs/hosted-advisory-rollout.md) documents the reader connection and TLS certificate settings; [operations](../docs/operations.md) documents deployment and monitoring.

## Endpoints and checks

- `/api/ready`: application/database readiness; used by Docker.
- `/api/health`: official advice and score freshness; 503 for stale/incomplete/unavailable data.
- `/api/refresh-status`: separate source retrieval and score publication dates.
- `/api/scoring-status`: supported formula, schema readiness and publication coverage.

```sh
npm run test:queries
npx tsc --noEmit
npm run lint
npm run build
```

`npm run test:postgres` requires the local fixture database. `npm run test:browser` requires the containerized fixture website at `http://localhost:3001`; run `bash scripts/check_containers.sh` from the repository root first. Browser tests target localhost fixtures and never modify production. See [verification evidence](../docs/v2-verification.md) for the separate read-only live checks.

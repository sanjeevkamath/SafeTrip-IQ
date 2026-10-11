# Phase 4 checkpoint 5: retries and freshness

## Fetch retries

Remote advisory fetching makes at most three attempts. Connection failures, timeouts, and HTTP 429/500/502/503/504 can retry, waiting one second and then two seconds. Each request has a five-second connect timeout and a twenty-second read inactivity timeout. These are not a strict total job deadline. Certificate errors and other HTTP errors fail immediately. XML parsing and model/database errors are not retried by this mechanism.

This retries only fetching, before any application data is changed. Once attempts are exhausted, the run fails and the published dataset remains available. Local XML ingestion does not perform network retries. Retry delays are deliberately capped; server Retry-After hints are not currently used.

## Public refresh timestamp

Migration `0005` adds the single-row `refresh_status` table. It contains only the completed refresh's publication time and source kind. The worker updates it in the same transaction as final scores. Failed refreshes, intermediate writes, and standalone score recalculations cannot advance this timestamp.

The website reader can read that table but cannot write it or access private run history. The homepage calls `/api/refresh-status` and shows the publication time. More than 48 hours is flagged as overdue, an initial operational threshold for the planned daily schedule. This threshold measures refresh age, not whether the original advisory is still valid or whether frozen clustering inputs are recent.

Local XML is explicitly labeled as local XML. Legacy Supabase returns unknown until its production schema/workflow is adopted. A database error is shown as temporarily unavailable. Development seeding clears the timestamp so restored examples cannot look like a freshly published live dataset. The browser checks on page load; continuous polling is not implemented.

## Operator status

```sh
bash scripts/worker_local.sh status --output .local/demo/refresh-status.json
cat .local/demo/refresh-status.json
```

Choose a fresh output filename each time. This read-only report includes the last completed publication and running attempts older than one hour. Such attempts may be slow or abandoned; the command does not change their status or kill jobs. The earlier refresh lock prevents overlapping cooperating writers. Investigate process/database connection state before manually resolving an abandoned receipt.

After applying migrations, test the public display with `cd frontend && npm run dev:local`. Run a local fixture refresh with `--write --publish-scores` to populate the timestamp, then reload the homepage. It will identify the source as local XML. Rebuild containers before testing the same changes through Compose.

## Verification and remaining work

Tests simulate recoverable errors, retry exhaustion, non-retryable errors, and no real waiting. Database tests prove freshness rolls back with a failed commit, old running attempts are reported, and the reader cannot modify status. Frontend checks cover legacy/seed unknown states and failed connections.

Full-country import and clustering mapping verification, broader browser coverage, retention/recovery procedures, and the final Stage 4 CI/preview review remain. This checkpoint does not deploy or schedule the worker, retrain models, or change production data.

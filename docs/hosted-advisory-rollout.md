# Hosted advisory rollout

## Current boundary

Supabase remains the hosted PostgreSQL database. Migrations through `0007` are for the local migration chain; they have not been applied to Supabase. Do not run `alembic upgrade head` on an existing hosted database: revision `0001` creates tables that already exist there. Do not stamp a revision without first verifying its schema and permissions.

## First: read-only hosted audit

Open the project's Supabase dashboard → SQL Editor → New query. Paste the complete contents of `db/scripts/audit_hosted_advisories.sql` and run it. It uses a read-only transaction and returns one JSON result containing schema structure, permissions, country codes and migration-table presence. It does not select credentials, advisory text, or score rows. Share the `audit` JSON for review. The final COMMIT may display a success message; the SELECT result contains the JSON.

Also check Settings → Data API → Exposed schemas and report the schema names. Do not add `advisory` to that list. Do not share passwords, API keys, or connection strings.

After reviewing the audit, prepare a hosted-specific migration, verified schema/policy backup plus an appropriate data recovery plan, restricted roles, and a local rehearsal against the captured structure. This work must precede hosted writes. Check every import target against `public.countries`; do not invent missing catalogue rows.

## November 4 hosted audit and prepared bridge

The provided audit reports PostgreSQL 17.6, six legacy application tables with RLS, no `advisory` schema, no SafeTrip database roles or Alembic table, and 249 country keys. Existing table/column grants show no anonymous/authenticated writes. Exposed schemas remain `public` and `graphql_public`. Comparing the complete saved capture against the catalogue found only `XKX` missing; `ATA` and `PSE` are present.

`db/hosted/001_advisory_foundation.sql` is the standalone bridge for this audited state. It creates the run ledger and raw capture tables, seven private advisory tables, the display view, and two restricted NOLOGIN roles. It adds Kosovo under the application's `XKX` key. It does not change existing scores, clustering, BERT data, or old advisory rows. The writer can read countries and insert advisory history; it cannot write the legacy tables. It is therefore intentionally unable to run legacy score-refresh commands.

The script uses one transaction, bounded lock/statement timeouts, preconditions and permission assertions. Unexpected state or an attempted rerun fails and rolls back. It revokes new-object API grants explicitly, including `service_role`; existing legacy service-role access is unchanged. It grants neither role membership nor passwords. It does not stamp Alembic: this hosted bridge is a separate migration path, not a claim that revisions 0001–0007 all exist on hosted Supabase. Later hosted changes must build on this bridge explicitly.

The bridge reuses the reviewed local migration DDL. Regenerate and rehearse with:

```sh
.local/database-venv/bin/python db/scripts/build_hosted_advisories.py
.local/database-venv/bin/python db/scripts/rehearse_hosted_advisories.py
```

The rehearsal uses a disposable localhost-only Docker PostgreSQL container with synthetic legacy records and Supabase-style default API grants; it never connects to Supabase. It checks actual ingestion/replay, role boundaries, score preservation and rerun refusal. This checks compatibility against a reconstruction of the audited structure, not a restore of the live database.

### Before applying the hosted bridge

From the repository root, take fresh backups using the existing local configuration and downloaded CA certificate. Do not paste `.env` contents or change it to a local fixture URL:

```sh
uv run --frozen python db/scripts/backup_schema.py
uv run --frozen python db/scripts/capture_data_baseline.py
```

If `pg_dump` is not on PATH, the schema command supports `--pg-dump` with the absolute path to your installed PostgreSQL client. Confirm both commands report success. Files and manifests remain in ignored `.local/supabase/` and `.local/baselines/`; share only success messages or errors with suppressed connection details. The data JSON export plus schema export is a recovery input, not an automatically tested full Supabase restore. Retain these files before any hosted change.

After those backups succeed, the reviewed bridge can be pasted into Supabase SQL Editor and run as `postgres`. A successful run leaves the roles NOLOGIN: authentication setup, hosted ingestion and Vercel configuration are separate steps. Keep `advisory` off the exposed-schema list. Do not try the local Alembic upgrade command on hosted Supabase.

If installation fails, do not disable the assertions or substitute `IF NOT EXISTS`: preserve the error and re-audit. On success, rerun the read-only audit for verification before configuring credentials. Do not drop new tables as a rollback once ingestion has begun; disable the new login/read path and retain the history pending review.

## Configure the restricted hosted writer

The post-install audit supplied on November 4 matches the intended roles, seven private tables, two ledger/capture tables, display view and 250-country catalogue. Existing public read grants are retained. The new roles remain NOLOGIN in that audit. This validates the inspected metadata, not live page rendering or score equality.

Run from the repository root:

```sh
uv run --frozen python db/scripts/hosted_advisories.py setup
uv run --frozen python db/scripts/hosted_advisories.py check
```

Setup uses the existing `SUPABASE_DB_URL` admin session-pooler configuration and CA locally. It generates a random writer password, saves the writer connection in `.local/supabase/advisory-writer.json` with mode 0600, hashes the password locally with libpq SCRAM, and enables only the writer login. Repeating setup reuses that private credential for the same target, allowing recovery from an interrupted attempt. Do not delete or share that file. The reader and Vercel settings remain unchanged. Setup changes a role credential; it does not import source data.

The check verifies TLS, actual `current_user`, role attributes and memberships, intended grants, and absence of legacy table/column write privileges. It executes only reads. A pooler login uses `safetrip_writer.<project-ref>` while the actual database role is `safetrip_writer`; see [Supabase connection documentation](https://supabase.com/docs/guides/database/connecting-to-postgres). The worker accepts this login format only on the Supabase session pooler with certificate verification; query parameters cannot override the checked login/target.

After setup and check succeed, capture, preview, then explicitly ingest a small real sample:

```sh
uv run --frozen safetrip capture-advisories --iso3 CAN --iso3 JPN --iso3 USA --output .local/v2/hosted-smoke/capture.json
uv run --frozen safetrip ingest-advisories --input .local/v2/hosted-smoke/capture.json --output .local/v2/hosted-smoke/preview.json
uv run --frozen python db/scripts/hosted_advisories.py ingest --input .local/v2/hosted-smoke/capture.json --output .local/v2/hosted-smoke/committed.json
```

By default the hosted helper accepts only CAN/JPN/USA. Full-destination mode requires explicit flags and a matching preflight plan as described below. It validates the capture and restricted connection before using the existing atomic ingestion code. It reserves a new output path before writes. A completed run ID and successful command are authoritative; an empty result file is not proof of success. Use a new result filename for a replay. No models or public score publication are involved.

## Local website read path

Migration `0007` adds `public.advisory_summaries`, a deliberately owner-rights view: only `safetrip_reader` gets SELECT. The view's owner can read the private source tables; the website role cannot. It projects an explicit list of public display fields, not raw payloads, run metadata, paragraphs, or NLP results. Hosted installation must explicitly revoke Supabase's default anon/authenticated grants and verify ownership/default privileges; the local migration is not a hosted security script.

For each source document, it selects the latest observation from a successful run, ordered by source retrieval time. Replaying an old capture does not make it current. Ties prefer the most recently stored normalization, then completed run and version ID. Sources retain separate documents, warnings and regional coverage; overlapping documents are not averaged or silently discarded. Unresolved coverage is excluded from country summaries but retained privately for review. This is a latest-known view, not a source-withdrawal or stale-document detector.

`GET /api/advisories?iso3=CAN` returns the country and separate `us_state` / `uk_fcdo` objects, each with `status` and `documents`. A known country without mapped observations has `not_available`; that does not mean safe, withdrawn, or no source document exists. Unknown country returns 404, malformed code 400, failed/unconfigured backend 503. Regional labels and independent levels remain visible in the response. UK empty warning flags remain distinct from a missing document.

The endpoint supports the explicit PostgreSQL backend or a dedicated `SAFETRIP_ADVISORY_DATABASE_URL` connection alongside legacy Supabase reads. Without either connection it returns 503. Existing endpoints are unchanged. The country-page section is opt-in through the server-only `SAFETRIP_ADVISORIES_ENABLED=1` setting. No score formula changes are part of this step.

To verify locally from the repository root:

```sh
bash scripts/check_database.sh
cd frontend
npm run dev:local
```

In another terminal:

```sh
curl 'http://localhost:3000/api/advisories?iso3=CAN'
```

This reads the fixed local database. Populated results require a successfully committed local advisory import; otherwise the response correctly reports missing data. Never use the example local passwords on Supabase.

## Restricted reader and local display preview

The user confirmed the hosted five-document import and replay: five new versions initially, then zero new documents/versions and five reused versions. The display query returned CAN/JPN advice from both sources and USA advice from the UK, with original retrieval timestamps. Full-world import has not happened.

Run from the repository root, one command at a time:

```sh
uv run --frozen python db/scripts/hosted_reader.py setup
uv run --frozen python db/scripts/hosted_reader.py check
uv run --frozen python db/scripts/hosted_reader.py dev
```

Setup enables only `safetrip_reader` with a generated SCRAM password stored in mode-0600 ignored `.local/supabase/advisory-reader.json`. The check verifies actual role, TLS, schema isolation, lack of table/column writes, intended public SELECT grants, and display-view reads. It reads no raw payloads. Do not share the credential file or put it in a NEXT_PUBLIC variable.

The dev command checks the reader, then launches the local Next.js app with three server-only environment settings: `SAFETRIP_ADVISORIES_ENABLED=1`, `SAFETRIP_ADVISORY_DATABASE_URL`, and `SAFETRIP_ADVISORY_DATABASE_CA` (certificate PEM). It reads the certificate and private file locally; no credential is passed in command arguments or written to frontend environment files. The existing frontend configuration continues to control scores, map, culture, and search. Vercel is not modified. Stop the preview with Ctrl+C.

Visit the local address Next prints, then `/country/CAN`, `/country/JPN` and `/country/USA`. Expect separate official-source cards, US level descriptions, UK warning labels, original region labels where applicable, source/retrieval dates in UTC, and official links. No imported source, an unavailable database, missing warning status, and an empty UK flag array have distinct messages. All overlapping documents remain visible individually. Displayed warnings do not alter scores or map colours. With the feature flag unset, the new country-page section is hidden.

Hosted advisory connections use the session pooler and an explicit certificate-verifying TLS object. The URL must have no query parameters: [node-postgres warns that URL SSL parameters replace explicit SSL options](https://node-postgres.com/features/ssl). Local tests use the restricted local reader without TLS. The web connection is independently pooled (maximum two connections per process); no raw-schema access is granted to the web role. Deploying the UI and configuring Vercel are separate later steps after preview review.

## Full-destination rollout

Start from merged main on a separate rollout branch. Capture/preview still require no database credentials. Use fresh output paths; partial captures and existing outputs are not overwritten.

For targeted source corrections, `preflight`/`ingest` also accept repeated `--iso3` values. The capture must have exactly that selection, and ingest requires the checksum/parser/selection-pinned preflight plan. This does not grant access to additional tables. The default CAN/JPN/USA sample path remains available; full captures still require `--all-destinations`.

```sh
uv run --frozen safetrip capture-advisories --all --output .local/v2/hosted-world-20261105/capture.json
uv run --frozen safetrip ingest-advisories --input .local/v2/hosted-world-20261105/capture.json --output .local/v2/hosted-world-20261105/preview.json
uv run --frozen python db/scripts/hosted_advisories.py preflight --all-destinations --input .local/v2/hosted-world-20261105/capture.json --output .local/v2/hosted-world-20261105/plan.json
```

Preflight is read-only. It checks the effective writer permissions, ensures every resolved country key exists in the hosted catalogue, and records exact input SHA256, parser version, both source counts, unresolved/overlapping review records, and previously stored documents absent from this capture. Inspect the saved plan before importing. Absence does not automatically withdraw a previously stored document; investigate unexpected gaps. Do not remove unknown destinations or force compound warnings onto one country to make validation pass.

When the plan matches the reviewed capture:

```sh
uv run --frozen python db/scripts/hosted_advisories.py ingest --all-destinations --plan .local/v2/hosted-world-20261105/plan.json --input .local/v2/hosted-world-20261105/capture.json --output .local/v2/hosted-world-20261105/committed.json
```

The full mode rejects a subset capture and requires the exact preflight checksum/parser/counts. It rechecks the catalogue immediately before invoking atomic ingestion. Both official sources must be present. Review-required documents remain retained, unresolved coverage stays out of the country display view, and overlapping mapped documents remain separate. No new table or public score migration is needed.

Verify the successful run and observations, then replay the same command with a new `replayed.json` output path: expect zero new documents/versions and all versions reused. The source counts depend on the captured feeds; the earlier 218/226 counts are not permanent constants. Use `hosted_reader.py check` and the opt-in local preview to verify the display, including PSE regional labels, ATA, a restriction-bearing UK page and one-source/missing-source cases. Vercel configuration, feature enablement and weekly AWS scheduling are separate steps.

Paragraph writes are batched per document through the driver, preserving original section/index identifiers and the all-or-nothing transaction. This avoids sending tens of thousands of separate paragraph INSERT round trips to the hosted database. Existing provenance, replay, and rollback integration checks apply to the batched path.

## Enable the existing merged display on Vercel

After verifying the full hosted import, open the existing Vercel project → Settings → Environment Variables. Add these three server-only variables for the Production environment. Leave the existing Supabase variables and database backend unchanged. No NEXT_PUBLIC reader password is needed.

Copy each value locally without printing it:

```sh
uv run --frozen python db/scripts/hosted_reader.py copy-env --name SAFETRIP_ADVISORY_DATABASE_URL
uv run --frozen python db/scripts/hosted_reader.py copy-env --name SAFETRIP_ADVISORY_DATABASE_CA
uv run --frozen python db/scripts/hosted_reader.py copy-env --name SAFETRIP_ADVISORIES_ENABLED
```

Run one command, paste its clipboard value into the matching field, then run the next. The database URL contains the restricted reader password: do not paste it into chat, screenshots, a GitHub secret discussion, or a public environment variable. The CA value is the full multiline PEM certificate. The feature flag value is `1`. The helper writes nothing to Git or frontend environment files.

Once all three values are saved, redeploy the current merged main deployment so the new environment settings take effect. Verify `/country/CAN`, `/country/JPN`, `/country/USA`, `/country/PSE`, `/country/ATA` and a restriction-bearing destination found in the capture. Check map/search and existing scores too. No score formula or map colour change is part of enabling these cards.

To disable the display, set `SAFETRIP_ADVISORIES_ENABLED=0` and redeploy; retain the stored advisory history. Full data storage and UI enablement are separate rollout actions. AWS schedules remain off.

### Verified hosted full import — November 5, 2026

The fresh capture contained 228 HTTP responses: the UK index, US RSS feed and 226 UK documents. It normalized to 218 US documents plus 226 UK documents, with 26,077 paragraphs and 228 mapped country keys. Hosted preflight found no missing catalogue keys and no previously stored documents absent from the capture.

The production import committed 439 new documents/versions and reused the original five. A full replay created zero new documents/versions, reused all 444 versions, and recorded 444 observations. Read-only verification checked paragraph counts for every document, the retained raw capture checksum, successful run status with zero published score rows, and exact equality of all 212 public score rows with the pre-migration snapshot. The display view returned 217 US and 224 UK records. Three unresolved compound documents remain private; the two Tonga documents remain separate mapped records. ATA has both sources, and PSE retains Gaza/West Bank regional records. Nonempty UK warnings were verified for AFG, AGO and ARM.

Generated capture, plan, committed result and verification evidence remain ignored under `.local/v2/hosted-world-20261105/`. This verifies hosted data storage and reader queries; it does not claim Vercel's live feature flag has been enabled.

The user confirmed the intended production site is `https://safetripiq.vercel.app/`, corresponding to the `safetripiq` Vercel project. Use that project for production environment settings; the repository also has another Vercel integration.

# Phase 0 security evidence and walkthrough

## Status — 2026-10-07

Complete for the scoped Phase 0 work. The owner supplied all 18 live role/table verification rows with expected_access=true, then confirmed deployed website behavior and Vercel public key/project configuration. Both client roles lack write/maintenance permissions, intended reads are preserved, service_role retains CRUD access, and RLS is enabled on all six tables. Schema backup, application-schema restore, and isolated permission tests passed. Limits of verification remain documented below.

## Findings from owner-supplied live catalog results

RLS is enabled on all six public tables: bert_scores, clustering, countries, culture, scores, travel_advisories.

Before containment, both anon and authenticated had table-level SELECT, INSERT, UPDATE, and DELETE permissions on all six tables. The pre-change policy inventory was:

| Table | Policy | Role | Operation | USING | WITH CHECK |
| --- | --- | --- | --- | --- | --- |
| countries | Allow public read for countries | PUBLIC | SELECT | true | — |
| countries | Allow public update for countries | PUBLIC | UPDATE | true | true |
| culture | Allow public read access to culture | anon | SELECT | true | — |
| scores | Allow public read access to scores | anon | SELECT | true | — |

This establishes an unrestricted countries UPDATE permission path for ordinary anon/authenticated roles at the grants/RLS layer. No production write was attempted. Constraints and triggers may still affect individual updates; Data API schema exposure and deployed project/key identity still need confirmation.

The other five tables have no reported write policy. Their direct client writes are denied by RLS despite the grants. This evidence does not establish that clients can modify scores. Role inheritance/bypass attributes, remaining column/default grants, and deployed configuration still need review.

At initial inspection, local root/frontend keys contained an anon role claim (decoded locally without logging credentials; decoding is not signature verification), and no backend writer credential was configured. The owner subsequently configured a separate backend credential; see the live connectivity checkpoint below. Local configuration does not prove Vercel's deployed configuration.

## Why the two layers matter

A grant permits an operation on a table. RLS limits which rows that operation may access. For this countries UPDATE policy, USING (true) allows every existing row and WITH CHECK (true) imposes no row restriction on the updated values. PUBLIC means every role, not a database schema. All-true policies can therefore leave a table effectively writable even with RLS switched on.

## First containment step

Run db/security/001_close_public_country_updates.sql in the Supabase SQL Editor. It drops only the known permissive UPDATE policy and revokes table UPDATE from PUBLIC, anon, and authenticated. SELECT access and table data remain unchanged. It is transactional and can be rerun. If a timeout/error occurs, issue ROLLBACK before retrying.

This intentionally disables anonymous country updates immediately. An old countries writer using the anon key can no longer update rows; this is the unsafe path being closed. Other anonymous writes were already blocked by the reported policies. The scripts still need an explicit backend credential transition and isolated writer verification. Do not run the population scripts to test production: they upsert real records and may overwrite fields.

The policy definition and effective privileges above preserve the known pre-change evidence. They are NOT a full schema/ACL backup: effective privilege results do not reveal grant provenance or grant options. Obtain a schema-only export including ACLs/policies, view/function definitions and triggers before broader permission changes. Do not commit private dumps or credentials.

## Verified after targeted containment

The owner supplied these live permission results on 2026-10-07:

| Role | countries SELECT | countries UPDATE | UPDATE on any countries column |
| --- | --- | --- | --- |
| anon | true | false | false |
| authenticated | true | false | false |

This confirms that direct country UPDATE access is denied at the privilege layer for both client roles, including effective column privileges. It does not test website behavior or prove that functions/views cannot write indirectly. No production write probe was performed.

## Verification checklist

- Complete: countries UPDATE policy removed; effective UPDATE grants removed.
- Complete: exposed objects, role memberships/flags, column and default grants audited.
- Complete: schema/ACL backup and isolated application-schema restore.
- Complete: backend credential configured and read-only SDK authentication verified.
- Complete: 56 denied local client operations and successful local service_role CRUD on all six tables.
- Complete: owner applied remaining table hardening; all 18 live verification rows match expected access.
- Complete by owner confirmation: deployed website search, map, and country detail smoke tests.
- Complete by owner confirmation: Vercel production key type/project identity and absence of privileged keys in NEXT_PUBLIC variables.
- Conditional: rotate privileged credentials if exposure is found. None has been established by this audit.

## Additional owner-supplied audit results

- Exposed Data API schemas: public and graphql_public.
- No functions in public.
- No views or materialized views in public.
- No non-internal triggers on public tables.
- graphql_public.graphql has arguments operationName text, query text, variables jsonb, extensions jsonb. It is SECURITY INVOKER (security_definer=false) and executable by both anon and authenticated.

The GraphQL entry point itself uses the caller's privileges, not its owner's privileges. These results reveal no elevated public function or custom trigger path. They are not an end-to-end GraphQL mutation test or an audit of extension internals.

## Backend writer transition — implementation checkpoint

All five writer scripts now call db/scripts/supabase_writer.py. The helper reads the ignored repository-root .env relative to its file location, respects existing process environment variables, and requires exactly one of SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY. It never falls back to ANON_KEY. A new-style secret must have the backend secret prefix; a legacy JWT must have a service_role claim. These are configuration guardrails, not cryptographic verification; Supabase authenticates the real credential.

The population script no longer logs a key prefix. The root .env and frontend/.env are ignored and untracked in the current checkout. No credential values were logged or copied into source. Git history and the deployed environment have not yet been fully audited.

The owner must add ONE credential to the root .env, not frontend/.env and not a NEXT_PUBLIC variable:

```dotenv
# Use the existing legacy service_role credential, OR the new-style secret alternative.
SUPABASE_SERVICE_ROLE_KEY=<value entered privately by the owner>
# SUPABASE_SECRET_KEY=<new-style backend secret entered privately instead>
```

Do not share the value in chat. Keep the frontend's anon key unchanged. The service role bypasses RLS and is an interim trusted-script credential; a scoped database writer role is planned later.

Do not execute populate_countries.py, populate_clustering.py, or modify_clustering.py as a credential test: they modify real data. Two existing population scripts also perform writes on import. The cluster remapping script remains non-idempotent; this security change does not make it safe to rerun. Use a separate read-only connectivity check and later an isolated write test.

Validation completed locally:

- `python3 -m unittest discover -s db/tests -v`: nine tests passed with fake credentials and mocked clients; no network requests.
- All database script files parsed successfully.
- `git diff --check` passed.

## Live read-only connectivity checkpoint

After the owner configured the root .env credential:

- Credential configuration accepted by the backend helper.
- Backend and local frontend URLs target the same project.
- Backend credential differs from the public frontend key.
- A SELECT of iso3, limited to one row, succeeded on countries and returned one row.
- The same bounded SELECT succeeded on bert_scores and returned one row.
- No record contents or credentials were printed. No INSERT, UPDATE, DELETE, or RPC was executed.

The check is saved as db/scripts/check_writer_connection.py. The existing base Conda environment had an incompatible combination (supabase 2.3.0 / httpx 0.24.1 / gotrue 2.9.1) and failed during client construction before any database request. A separate temporary environment at /tmp/safetrip-phase0-check was created with supabase 2.24.0 and python-dotenv 1.2.1, matching the repository's direct dependency versions. Existing environments were not changed. This is a temporary verification environment, not the final locked application environment.

## Verified backup and isolated permission tests — 2026-10-07

The owner supplied the Supabase root CA. TLS hostname/certificate verification and database authentication succeeded. The session pooler did not preserve the read-only startup option; catalog reads therefore explicitly set the transaction read-only. Client-to-pooler TLS was verified through libpq. pg_stat_ssl describes the pooler's server-side connection, not the local client's TLS connection, so it was not used as evidence of client transport security.

Completed backup: `.local/supabase/schema-backup-20261007T185555741322Z/`:

- schema.sql: complete database schema-only pg_dump, with owners and ACLs retained; 303,722 bytes.
- public-schema.sql: application-only schema for local restore.
- permissions.json: role flags, memberships, explicit column grants, policies, default ACLs, and effective permissions.
- manifest.json: hashes and scope. No application rows or role passwords were exported.

The directory is ignored by Git and private to the local user. The earlier complete backup is retained; the export interrupted by the connection loss has no completion manifest and must not be treated as complete. This backup represents the state AFTER the first countries UPDATE fix and BEFORE broader hardening.

The live catalog independently confirmed the countries UPDATE policy is absent, both client roles have no BYPASSRLS and no role memberships, and there are no explicit public-table column ACLs. Both roles still have excess table permissions including TRUNCATE. That grant is inappropriate but does not by itself establish an HTTP API path to execute TRUNCATE.

Temporary tools vanished after the interruption. Tools were recreated in the ignored `.local/security-tools` environment. The actual public-schema.sql was successfully restored into a dedicated local PostgreSQL 17 database, with local anon/authenticated roles and a local service_role carrying the backed-up BYPASSRLS attribute. No passwords or production rows were copied. The local server used a private Unix socket and no TCP listener.

Before production deployment, `db/security/002_client_read_only.sql` was applied to the local restore:

- Four intended role/table SELECT paths succeeded against synthetic rows.
- 56 unauthorized client operations failed with insufficient privilege (eight internal/disallowed reads plus 48 INSERT/UPDATE/DELETE/TRUNCATE attempts).
- service_role successfully inserted, updated, selected, and deleted synthetic rows on all six tables, including foreign-key-dependent records.
- Client write/maintenance privileges were absent, and future postgres-created public tables/sequences no longer inherited client privileges.
- Applying the migration twice succeeded.

Reproduction: restore the application dump into the dedicated `safetrip_permission_test` local database, provision the platform role names and flags locally, then run `db/tests/verify_client_permissions.py`. It deliberately has a fixed local socket/database target and never loads .env. Use a fresh restore for each run because its synthetic baseline seed rows persist in the disposable database; individual probes roll back.

The test validates PostgreSQL permissions, not HTTP gateway behavior, JWT authentication for writes, or a full Supabase platform restore. Existing read-only SDK connectivity has been verified separately. The complete all-schema dump has not been restore-tested; only the public application schema has.

## Live deployment verified — owner-operated dashboard

The owner applied `db/security/002_client_read_only.sql` in the Supabase SQL Editor. It revokes client privileges on the six known application tables, restores only existing intended read paths, and leaves service_role untouched. It retains the existing SELECT policies and RLS. It also removes automatic client grants on future public tables/sequences created by postgres. Defaults for the platform's supabase_admin role and function EXECUTE defaults are deliberately unchanged; new functions/other object creators require explicit access review.

The owner returned the results of `db/security/003_verify_client_permissions.sql`: all 18 rows have expected_access=true. Anon has SELECT on countries/culture/scores only; authenticated has SELECT on countries only; neither client role has table/column writes or maintenance privileges checked by the query. service_role has SELECT/INSERT/UPDATE/DELETE on all six tables. RLS is enabled throughout. These are live catalog checks; mutation tests were confined to the local restore.

The owner subsequently confirmed the deployed frontend configuration and website checks. Phase 0 is closed for the stated scope; no privileged credential exposure was established, so rotation was not indicated. This does not claim a forensic review of historical access or historical secret exposure.

## Interview explanation

“I found that enabling RLS alone had not secured our country table: a permissive UPDATE policy allowed every row, and public roles also held UPDATE grants. I separated the table permission check from the row-policy check, prepared a targeted transactional fix preserving reads, and verified permissions before testing the application. The wider audit covers functions and views because they can provide alternative access paths.”

Use past-tense claims about applying/verifying the fix only after those steps are completed.

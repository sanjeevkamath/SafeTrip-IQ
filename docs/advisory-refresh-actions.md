# Manual US/UK refresh with GitHub Actions

The workflow **Refresh official advisories** runs on GitHub-hosted Ubuntu when manually started on `main` or by the guarded weekly schedule, after successful CI for that exact commit. Scheduled writes require explicit activation and a verified end-to-end manual run; see [operations](operations.md). There is no AWS task, model download or retraining. A lightweight locked `advisory-refresh` dependency group installs HTTP and PostgreSQL clients without PyTorch, pandas or Transformers.

## What a run changes

1. Fetch the US feed and complete UK destination index/documents. Capture bytes and checksums without database access.
2. Use the restricted ingestion writer to validate the catalogue and existing source-document coverage. Missing keys, missing previously stored documents, failed fetches and parser errors stop the run. A legitimately withdrawn destination needs investigation and an explicit handling change; it is not silently removed or marked safe.
3. Import the complete, preflight-pinned capture into append-only advisory history. Matching content/parser versions are reused with new observations. Cards use these observations immediately; public score values are unchanged at this stage.
4. Use the restricted reader to calculate an exclusion-only scoring preview. Independently verify its checksum and formula; conflicting whole-country US levels stop progression. Explicitly unresolved compound destinations remain in the import plan for review and never become guessed national scores.
5. Only if **Publish scores** was selected, pass that run's exact preview to a separate job using the scoped publisher. The publisher checks live website readiness, current input fingerprint and output equality, then commits scores/history atomically.
6. Independently read scores back and check every result, formula/run reference, null and original BERT/clustering input against the preview. A discrepancy fails the job and preserves evidence; it does not silently retry or undo an already committed publication.

Source ingestion and score publication are separate transactions. A failure after import can leave newer advice cards beside the previous score publication. The run ledger and artifacts identify which stage committed. GitHub concurrency prevents this workflow from overlapping itself, while database locks protect individual ingestion/publication transactions; manual database operations can still invalidate a preview. Stale plans fail instead of overwriting newer inputs.

## One-time GitHub configuration

Use existing generated scoped account files; do not upload `.env`, an admin URL, Supabase service-role credentials, or the entire `.local` directory. The credential installer accepts only the expected role and five connection fields, requires verified TLS and private mode-0600 files, and rejects connection overrides. Database helpers also verify the actual effective role and permissions before use.

In repository **Settings → Environments**, create:

- `advisory-refresh`: restrict deployments to `main`; contains only the writer secret below.
- `score-publication`: restrict deployments to `main`; contains only the publisher secret below. For optional manual approval, enable **Required reviewers** and allow self-review for a solo operator. For the chosen automatic weekly publication policy, leave required reviewers off: validation and the scoped publisher guard writes. Enabling reviewers pauses scheduled publication until approval.

From the project directory, send the files directly to GitHub Secrets using stdin. These commands do not print the values:

```sh
# Repository secrets: shared read-only account and the TLS CA certificate.
gh secret set SAFETRIP_READER_CONFIG < .local/supabase/advisory-reader.json
gh secret set SAFETRIP_DATABASE_CA < .local/supabase/prod-ca.crt

# Environment secrets: keep the two write capabilities separate.
gh secret set SAFETRIP_WRITER_CONFIG --env advisory-refresh < .local/supabase/advisory-writer.json
gh secret set SAFETRIP_PUBLISHER_CONFIG --env score-publication < .local/supabase/official-score-publisher.json
```

The CA is a public trust certificate; storing it here keeps runner configuration together. No new database grants, credentials or Vercel settings are required. Account rotation later must update both the local private file and the corresponding GitHub secret. GitHub masks secret values, but the workflow never relies on masking to make printing a connection string safe.

## First runs

Merge this workflow, wait for main CI to pass, then open **Actions → Refresh official advisories → Run workflow**, choose `main` and leave Publish scores **unchecked**. This is a real advisory import, not a database dry run; scores remain unchanged. Inspect the Actions summary and download the `advisory-refresh-<run>-<attempt>` artifact to review the import plan, import result and scoring preview.

For an end-to-end run, start it again with Publish scores selected. It captures fresh inputs; it does not reuse the earlier run's preview. Inspect this new run's artifact/summary, especially coverage, changes, unresolved mappings and the input hash. If environment reviewers are enabled, approve that exact preview; otherwise publication proceeds automatically after validation. The successful publication summary records the run ID and independent verification result. Check a few live country pages, including regional-only destinations and a Level 4 country.

Artifacts are retained for 14 days and include public government-source responses, normalized plans, score snapshots and publication evidence. They contain no connection configurations. On a public repository, treat these artifacts as publicly accessible. Credentials are written only under `.local/supabase`, never uploaded or cached, and removed in an `always()` cleanup step on disposable runners.

If a run fails, review the failed stage and database run ledger before retrying, particularly if a publication result was ambiguous. Empty or partial JSON is not evidence of a commit. Prefer a new full workflow run rather than rerunning only a failed job: artifact names include the run attempt to avoid mixing evidence. Do not manually republish a successful preview; its input fingerprint is stale by design.

## Weekly scheduling and monitoring

The weekly cron, activation receipt, daily freshness monitor, notification setup and recovery procedure are documented in [operations](operations.md). Neither merging a cron nor setting a secret is sufficient to enable scheduled writes: the activation variables and a successful manual publication/read-back receipt are required.

This is data refresh automation, distinct from CI checks and worker-image publishing. It consumes GitHub Actions runner time and artifact storage; availability and allowance depend on the repository/account. No continuously running compute is introduced.

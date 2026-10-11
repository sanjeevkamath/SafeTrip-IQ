# Phase 4 checkpoint 2: run history and score provenance

The local Postgres worker now keeps a receipt for each write attempt. Current tables answer “what should the site display?”; history answers “which inputs produced this result, and did publication succeed?” This does not change the scoring formula or retrain either model.

## What is recorded

- `pipeline_runs`: run ID, command, start/finish times, running/succeeded/failed status, prepared input payload and its SHA-256, available version metadata, coverage, final-score row count, and exception class on failure.
- `score_history`: a snapshot of every published final score, its components, scoring version, and source records. Later publications leave these snapshots intact.
- Current component rows carry `last_run_id`. Current final scores also carry `published_at`, linking the displayed result to its publication.

New BERT inference records a fingerprint of the actual weights, configuration, and tokenizer files. XML ingestion identifies the current cleaner as `legacy-advisory-v1`; externally prepared scoring JSON has unknown cleaning provenance. Legacy seed rows have no verified model identity, so that information stays unknown. The stored advisory snapshot may be newer than a retained BERT component; the BERT input text and run reference distinguish them.

The run input snapshot is the prepared publication payload. [Checkpoint 3](phase-4-incremental-refresh.md) additionally retains original RSS bytes in a separate private table. Complete training/index provenance and code revision tracking remain future work. A publication timestamp is also not the source advisory's publication date.

## Transactions and access

The worker creates a running record before parsing or inference. Successful data changes, score-history inserts, and the succeeded status commit together. If publication fails, those changes roll back; a separate transaction records the failure. Failures before inputs are prepared may have no payload or hash.

Only the exception class is saved, not raw exception messages that could contain connection details. A killed process or lost database connection can leave a run marked running; automatic recovery is not implemented yet.

Both history tables use RLS and are private to the backend. The site reader cannot query them. The worker can insert score history but cannot update or delete it; it can update run lifecycle records. Database administrators retain control, so this is not a tamper-proof audit log.

## Try it locally

Apply migrations and restore the three development countries:

```sh
bash scripts/setup_local_db.sh
```

With the local model checkpoint available, run one fixture refresh and publish:

```sh
bash scripts/worker_local.sh refresh \
  --input tests/fixtures/advisories.xml \
  --output .local/demo/history-refresh.json --write --publish-scores
```

Read the latest 20 run summaries:

```sh
bash scripts/worker_local.sh runs --output .local/demo/run-history.json
cat .local/demo/run-history.json
```

Use a new output filename each time; existing files are not overwritten. `runs` and score previews do not create run records. An output JSON file alone does not prove a commit: check the run's status. Intermediate-only writes can succeed with `published_rows: 0`, because that count refers to final scores.

The three countries are intentional local fixtures. The frozen regression tests exercise all 212 captured scores; a controlled import of the full dataset comes later. Re-running local setup restores fixture values and clears their current run pointers, while keeping historical receipts.

This feature applies to the Postgres backend. These migrations and writes have not been applied to hosted Supabase. Rebuild migration/worker containers before using the new behavior there.

## Verification and next checkpoint

`bash scripts/check_database.sh` verifies successful history, exact input hashes, preserved snapshots, rollback, safe failure records, preview behavior, and access restrictions in disposable local databases. The current suite passes 23 database integration tests and 26 lightweight tests; all 212 baseline scores still match.

Repeated identical inputs create new receipts. [Checkpoint 3](phase-4-incremental-refresh.md) skips inference when cleaned content and inference provenance match. [Checkpoint 4](phase-4-missing-advisories.md) handles missing advisories and overlapping refreshes. Freshness reporting, retention, and retries remain open.

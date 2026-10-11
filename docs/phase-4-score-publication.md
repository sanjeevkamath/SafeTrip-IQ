# Phase 4 checkpoint 1: final-score publication

The Postgres worker can now calculate the displayed `scores` rows from the stored BERT classes and verified clustering risk tiers. The first checkpoint preserves the captured formula and adds explicit publication. [Checkpoint 2](phase-4-run-history.md) adds run history; incremental inference, feed coverage rules, and scheduling remain later work.

## Missing components are handled explicitly

| Available inputs | Calculation | Example |
| --- | --- | --- |
| Both | Mean of `10 - 2.5 × BERT` and `10 - 2 × cluster tier` | BERT 3, tier 4 → 2.25 |
| BERT only | `10 - 2.5 × BERT` | BERT 3 → 2.5 |
| Clustering only | `10 - 2 × cluster tier` | Tier 2 → 6 |
| Neither | SQL NULL | No numeric score |

Zero is a valid class/tier, not missing data. The implementation calls the existing pure `legacy_safety_score` function, keeping one source of truth. Its `legacy-v1` name identifies behavior, not scientific accuracy. Tests publish all 212 frozen scores through Postgres: 164 have both components, 44 BERT only, and four clustering only. The result matches every captured score exactly.

Publication considers every country in the catalog with LEFT JOINs to the component tables. It inserts a `scores` row even when both components are absent, with a null final score; a previously stored number is cleared if both stored components are now absent. It preserves countries with only one component. [Checkpoint 4](phase-4-missing-advisories.md) clears missing advisory/BERT components during a successful complete final refresh. Existing score rows referencing an unknown country cause a failure instead of silently being retained or deleted. Empty country catalogs and invalid component ranges also fail.

## Raw cluster IDs are not risk tiers

Migration `0002` adds `clustering.score_kind` with values `unverified`, `raw_cluster_id`, or `risk_tier`. Existing rows default to `unverified`: the migration cannot infer their meaning. The local seeds explicitly mark their captured values as risk tiers. `import-clusters` always marks its output as raw IDs, even if a caller supplies a different marker. Final publication refuses any non-null clustering value that is not marked `risk_tier`.

This marker is an explicit assertion by a trusted writer, not a statistical evaluation or complete model provenance. Production adoption must review the original mapping before marking existing rows as risk tiers. Do not mark raw IDs as tiers merely to bypass the check. The automatic centroid-to-tier mapping and versioned index/model releases are later work.

## Try it locally

Update the local schema and restore the documented seeds:

```sh
bash scripts/setup_local_db.sh
```

Preview scores from current local database components, using a new output path:

```sh
bash scripts/worker_local.sh publish-scores \
  --output .local/demo/final-score-preview.json
```

Unlike the original artifact-only preview commands, `publish-scores` must read the database, including its internal component tables. It uses the writer account for those reads but does not change database rows unless `--write` is present. The artifact contains a scoring version, coverage counts, and all proposed score rows.

After inspecting the preview, recalculate and publish from the current database:

```sh
bash scripts/worker_local.sh publish-scores \
  --output .local/demo/final-score-publication.json --write
```

The second command recalculates current inputs; it does not apply the previously saved preview. A score/model version approval workflow is not implemented yet. Existing output files are never overwritten. The JSON is saved before database commit and may remain after a failure, so the artifact alone does not prove publication.

To publish an advisory refresh, its BERT predictions, and final scores together:

```sh
bash scripts/worker_local.sh refresh \
  --input tests/fixtures/advisories.xml \
  --output .local/demo/refresh-with-final-scores.json \
  --write --publish-scores
```

This requires the local checkpoint. `score` also supports `--write --publish-scores`. Without the new flag, existing score/refresh commands still update only intermediate data. Final publication is supported only by the Postgres backend; the Supabase API adapter rejects this request before creating a client.

Containers must be rebuilt to include the command and new migration:

```sh
docker compose build migrate worker
docker compose run --rm migrate
docker compose run --rm seed
docker compose run --rm --no-deps worker publish-scores \
  --output /output/final-score-preview.json
```

The Compose seed job restores development examples. Use the host setup command or these container commands, not both. Production schema application and production score publication have not been performed.

## Atomicity and limits

The Postgres transaction encloses input writes, missing-advisory clearing, and final-score calculation/upserts. An error after the first final-score row is written rolls back the entire transaction, including earlier advisory and BERT updates. Database advisory locks protect both publication and, since checkpoint 4, the complete refresh lifecycle. Manual SQL and older writers do not participate in these locks.

All final rows are validated before final upserts begin. Repeating the same inputs gives the same scores and no duplicate current rows. Each write attempt now has a durable run record, but this is not yet complete refresh idempotence: advisory fetch timestamps still change and there is no retry protocol. Final scores use all components remaining after any complete-feed removal policy is applied.

Run checks with `bash scripts/check_database.sh`. New tests use a uniquely named disposable local database and remove it afterward. They cover all four availability cases, all 212 regression fixtures, unchanged previews, repeat publication, successful atomic refresh, injected mid-publication failure, bad component ranges, raw/unverified clusters, concurrent publication, and CLI preview/write behavior.

Run history is covered in [checkpoint 2](phase-4-run-history.md), incremental scoring in [checkpoint 3](phase-4-incremental-refresh.md), and missing-advisory policy in [checkpoint 4](phase-4-missing-advisories.md). Retries and freshness reporting remain next.

Verification: 18 local database integration tests and 25 lightweight Python/credential tests passed, and all 212 frozen scores matched both offline and after database publication. The standalone preview command also completed against the seeded Compose database without changing its rows. All publication-failure tests used disposable local data. These changes have not been applied to production.

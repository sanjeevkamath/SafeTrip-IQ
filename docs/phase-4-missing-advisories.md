# Phase 4 checkpoint 4: missing advisories and refresh ownership

## Missing means blank

A successful Postgres `refresh --write --publish-scores` treats the incoming feed as the complete advisory snapshot. Countries absent from it lose their current advisory and BERT component. Their historical run records and score snapshots remain available.

| Current inputs after refresh | Published result |
| --- | --- |
| Advisory/BERT and clustering | Existing combined formula |
| Advisory/BERT only | BERT-only score |
| Clustering only | Clustering-only score, blank BERT component |
| Neither | NULL final score, never zero |

The country catalog and clustering rows are preserved. Run metadata records the missing ISO3 identifiers, their count, and the number of advisory/BERT rows cleared. Clearing, new predictions, final-score recalculation, and success/history records commit together. An error rolls everything back.

Fetch or parser failure is not evidence that every country has lost its advisory. Empty input, unmapped/unknown countries, duplicate mapped input rows, or missing/duplicate predictions prevent publication. The existing parser still retains its historical last-entry-per-ISO3 deduplication; revisiting duplicate source entries is separate work.

A valid but incomplete source response cannot automatically be distinguished from intentionally removed advisories. This rule therefore assumes the successful feed is authoritative. In particular, a local XML passed to final refresh must represent the complete intended snapshot for that database. Use fixtures only against the local development database. Coverage-drop monitoring remains future work.

Standalone `ingest`, `score`, and refreshes without `--publish-scores` remain intermediate updates and do not apply this removal policy. Use the full refresh command for a coherent published snapshot. `publish-scores` recalculates stored components; it does not fetch a feed or infer which advisories disappeared.

Old source dates do not by themselves cause removal: an unchanged advisory can remain current for a long time. [Checkpoint 5](phase-4-retries-freshness.md) adds fetch retries, refresh-age reporting, and a read-only report of overdue running attempts.

## One refresh at a time

The Postgres worker obtains a session advisory lock before fetching or inference and holds it until publication finishes. A second cooperating refresh fails before fetching. Other worker write commands also check this lock before modifying data.

The run record starts before lock acquisition, so rejected attempts appear as failed runs. Successful publication, handled failure, and closing the database session release the lock. An abruptly killed process may leave its receipt marked running, while PostgreSQL releases its lock when the connection is closed/detected as lost. Automatic receipt reconciliation remains future work.

The lock requires a direct PostgreSQL connection or a session-compatible pooler. Do not use transaction-mode pooling for the worker's session lock. Hosted connection selection remains part of deployment. Manual SQL and older writers that ignore the advisory lock can still modify data.

## Local command and verification

With the local database and checkpoint ready, use an unused output path:

```sh
bash scripts/worker_local.sh refresh --input tests/fixtures/advisories.xml \
  --output .local/demo/missing-policy-refresh.json --write --publish-scores
```

These fixtures contain Canada and Japan; the US keeps its clustering-only score. The stronger removal cases are tested in a disposable database with previously populated advisory and BERT rows:

```sh
bash scripts/check_database.sh
```

Tests verify missing BERT-only countries become NULL, clustering survives, old history survives, invalid inputs preserve data, a mid-publication failure restores cleared rows, and overlapping workers fail before fetching. No hosted schema change is needed for this checkpoint.

## Model maintenance decision

Clustering is a frozen legacy artifact for now. Preserve the source data, available transformations, mapping, and checksums that we can verify; document gaps and data age. Rebuilding it annually is not a prerequisite for deployment, and it must not be described as a fully reproducible training pipeline until its provenance supports that claim.

BERT retraining can be manually triggered later. That workflow needs a versioned dataset, reviewed cleaning and label rules, a trustworthy held-out evaluation set, comparison with the current model, and explicit promotion of an accepted checkpoint. The known train/test overlap must be addressed before reporting evaluation accuracy. New approved model bytes automatically invalidate inference reuse. Routine advisory refresh performs inference only.

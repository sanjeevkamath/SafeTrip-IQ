# Phase 4 checkpoint 3: incremental advisory inference

Postgres `refresh --write` now compares each incoming advisory with its stored BERT prediction. It runs inference only for new or changed inputs. It does not train a model.

## Reuse rule

A prediction is reusable only when all of these match:

- The SHA-256 of the exact cleaned text passed to BERT.
- The fingerprint of model weights, tokenizer, and configuration files.
- The cleaning version and inference version (currently CPU classification with a 256-token limit).
- An original run with succeeded status and a valid class between 0 and 3.

Legacy rows with unknown provenance are scored again once. Source date or HTML formatting changes that leave cleaned text unchanged do not require inference. Changing the cleaner, model, or inference version invalidates reuse. Keep the inference version up to date when changing tokenization or prediction behavior.

Final-score calculation still runs when `--publish-scores` is supplied, including on a fully reused batch. A change to final-score mathematics therefore takes effect without needing to rerun BERT. Clustering-only countries remain included. [Checkpoint 4](phase-4-missing-advisories.md) clears advisory/BERT components absent from a successful complete refresh.

## Original inputs and provenance

Every CLI ingestion saves the exact XML bytes to `<output>.source.xml` before parsing. With a Postgres writer, migration `0004` also retains the bytes, hash, receipt time, and run ID in the private `raw_feeds` table. A failed parser leaves that evidence available. Fetch failures have no response body to save. The receipt time is separate from the source date inside the XML.

The worker can insert/read raw feeds but cannot update/delete them; the web reader cannot access them. Each attempt retains its own copy, even when unchanged. Retention and cloud artifact storage are still future work.

New predictions point to the new run. Reused predictions retain their original run IDs; the refresh artifact lists them in `reused_bert_scores`, while `bert_scores` contains only new predictions. Run metadata records `advisory_count`, `predicted_count`, and `reused_count`. Final-score history captures the original prediction provenance alongside the newly fetched advisory.

Before committing, the publisher locks and checks reused prediction rows. If another writer changed one after the reuse decision, the refresh fails and rolls back. [Checkpoint 4](phase-4-missing-advisories.md) also prevents cooperating refresh jobs from overlapping.

## Try two local refreshes

Apply migrations and reset the development fixtures once:

```sh
bash scripts/setup_local_db.sh
```

Then run twice with different output paths, without resetting the database between runs:

```sh
bash scripts/worker_local.sh refresh --input tests/fixtures/advisories.xml \
  --output .local/demo/incremental-1.json --write --publish-scores
bash scripts/worker_local.sh refresh --input tests/fixtures/advisories.xml \
  --output .local/demo/incremental-2.json --write --publish-scores
bash scripts/worker_local.sh runs --output .local/demo/incremental-runs.json
```

Expected: the first run infers two advisories; the second infers zero and reuses two. Both publish three final scores because the third local country has only a clustering component. The second run still hashes model files but does not load BERT. Choose unused output paths, including their `.source.xml` companions, when repeating the demonstration.

Artifact-only previews and the legacy Supabase adapter still score every advisory. Incremental reuse currently applies only to Postgres write refreshes. Rebuild worker and migration images before using it through Compose.

## Verification

Tests cover zero-valued classes, changed text/model/cleaner/inference versions, unknown provenance, preserved prediction origins, concurrent cache changes, malformed-feed retention, and raw-feed permissions. Existing atomic-publication and all 212 score-regression checks remain in place.

Missing-advisory policy and refresh overlap protection are implemented in checkpoint 4. Bounded retries and freshness reporting remain next. No scheduling or hosted migration has been enabled by these checkpoints.

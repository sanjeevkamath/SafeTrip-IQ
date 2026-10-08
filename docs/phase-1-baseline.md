# Phase 1 — Capture reproducible behavior

Before changing architecture, capture what the system currently does. A regression check answers “did this refactor change the result?” It does not establish that the result is scientifically correct.

## Current data flow

The website reads `countries`, `culture`, and `scores` through the Supabase public client. Trusted Python scripts write intermediate advisory classifications to `bert_scores` and country risk tiers to `clustering`. Historical SQL copies those intermediate values into `scores`. The original SQL that calculated `safe_trip_score` has not been recovered.

The supplied INSERT references `clustering_scores`, but the current database table is `clustering`. The supplied UPDATE uses the current table name. Neither statement calculates a final safety score; both copy component values. The UPDATE only affects existing `scores` rows, so it does not introduce newly scored countries.

## Recovered scoring rule

A read-only, repeatable-read database snapshot at `20261008T032611470774Z` contained:

| Table | Rows |
| --- | ---: |
| countries | 249 |
| culture | 248 |
| scores | 212 |
| bert_scores | 208 |
| clustering | 168 |
| travel_advisories | 209 |

Full exports remain under ignored `.local/baselines/`. Only the 212 public score tuples needed for regression checks are included in `tests/fixtures/legacy_scores.json`.

The following inferred rule matches **all 212 stored final scores exactly**:

```text
advisory safety = 10 - 2.5 × bert_score          # class IDs 0..3
cluster safety = 10 - 2.0 × clustering_score    # risk tiers 0..4
final score = mean of whichever components are present
```

There are 164 rows with both components, 44 with only BERT, and four with only clustering. Available intermediate components match the corresponding copied values in `scores` in this snapshot.

For example, Afghanistan has components 3 and 4: `(2.5 + 2) / 2 = 2.25`. Canada has components 0 and 0, giving 10. The United States has only clustering tier 2, giving 6.

Multiplying by 2.5 was part of the BERT conversion, but reversing direction also matters: larger class IDs represent greater advisory severity, while larger displayed scores represent greater safety. This legacy rule does **not** span the full 0–10 range: the BERT component bottoms out at 2.5 and clustering at 2. The implementation preserves that behavior instead of silently rescaling existing results.

`pipeline/scoring.py` contains this inferred rule. It returns `None` when both components are missing, an explicitly defined edge case absent from the snapshot. The function is currently an offline baseline; production writers have not been changed to publish recalculated scores.

## Reproduce it yourself

From the repository root:

```sh
python3 -m scripts.verify_baseline
python3 -m unittest discover -s tests -v
```

No credentials, network access, model downloads, or database writes are needed. The verifier checks frozen input hashes and every captured final score. The unit tests also cover missing and invalid components.

For model and clustering checks:

```sh
uv sync --frozen
uv run --frozen python -m scripts.verify_baseline --with-model --with-clustering
uv run --frozen python -m unittest discover -s db/tests -v
```

`pyproject.toml` declares dependencies; `uv.lock` records their resolved versions and artifact hashes. Python is constrained to 3.11. The supported lock targets are Apple Silicon macOS and Linux x86_64. Linux uses the explicit CPU PyTorch index. The new environment was exercised on macOS; Linux execution still needs verification in the container milestone.

The requirements file is a compatibility export. Prefer `uv sync --frozen`, which scopes the CPU package index to PyTorch. Optional `research` dependencies support training and analysis; optional `audit` dependencies support the read-only database utilities.

## What the ML checks establish

The local `results/checkpoint-189` inference artifact consists of six files recorded in `docs/baseline/artifacts.json`, about 438 MB total. Only safetensors weights and local tokenizer/configuration files are loaded. Training optimizer files are not needed. Hashes identify the exact bytes used.

The checkpoint remains ignored by Git. A new clone can reproduce final scores and clustering, but model inference additionally requires obtaining those six files from the maintainer. Versioned artifact distribution remains future work.

Two synthetic advisory texts have captured class predictions. They check inference stability after dependency changes, not correctness. In particular, the severe synthetic advisory maps to class 1 in this checkpoint; this is not a ground-truth label. The current training code maps labels 1–4 to class IDs 0–3, but the checkpoint stores generic label names and its exact original training provenance is unverified.

Clustering reproduces all 168 saved country cluster IDs using the frozen feature CSV, five clusters, random state 42, and `n_init="auto"`. Its historical fit includes 169 rows, one without an ISO3 identifier. The baseline preserves that population. Raw cluster IDs are distinct from the manually remapped risk tiers stored in the database. Persisting fitted preprocessing and centroids, and replacing manual tier assignment, remain later work.

## Known limitations and next work

- The training and test CSVs share 136 distinct advisory texts after trimming and lowercasing. Existing validation metrics are not a defensible independent test result. Split design, deduplication, and evaluation need repair before making accuracy claims.
- The scraper's default ISO lookup file, `db/scripts/wikipedia-iso-country-codes.csv`, is missing. Its location can now be configured with `SAFETRIP_ISO_CSV`, but end-to-end fresh ingestion is not yet reproducible.
- Historical preprocessing assets and training provenance are incomplete. Frozen-feature clustering reproduction is narrower than rebuilding the dataset from its upstream sources.
- The production frontend build initially passed with the existing installation. The CI milestone subsequently verified a clean `npm ci`, TypeScript, lint, and build in an isolated macOS copy with dummy Supabase configuration. The first GitHub Linux run remains pending.
- Some legacy ingestion scripts still execute work on import. Do not import or run them against production for testing. The verifier avoids those scripts.

The next milestone is basic CI and a clearer project structure, followed by a disposable local PostgreSQL environment. The baseline gives those refactors an explicit behavior to preserve. No production data was changed while capturing or verifying it.

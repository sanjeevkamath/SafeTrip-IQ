# Official US advisory plus existing clustering

Scope decision: defer new external indicators and new NLP scoring. Replace the BERT input in the legacy composite with the actual US advisory level, preserving the existing conversions and equal weights as an application policy. UK warnings remain a separate source-backed display; BERT remains experimental.

## Preview formula

- US level 1–4 becomes `10 - 2.5 * (level - 1)`: 10, 7.5, 5, 2.5.
- Existing published clustering tier 0–4 keeps `10 - 2 * tier`: 10, 8, 6, 4, 2.
- Two components are averaged equally. One available component is used alone and labelled accordingly. Neither available produces null, never an imputed safe score.
- Formula `us-official-cluster-v1` records the regional policy separately. These are ordinal-to-display conversions, not probabilities of harm or a statistically calibrated travel-safety scale. Level 4 remains explicitly flagged; no numerical cap has been silently introduced.

The clustering inputs come from existing published `scores.clustering_score`, not a fresh K-means fit or arbitrary raw cluster IDs. Comparison of the pre-migration snapshot found all 168 published clustering values equal to the corresponding stored clustering values. This preserves the existing asserted risk-tier interpretation; it does not independently validate the original manual tier ordering or data vintage.

For multiple mapped whole-country US documents, equal levels contribute one component while all source documents remain in the report. Disagreeing levels block publication rather than silently choosing a winner. **Confirmed policy: exclude regional-only US levels from the countrywide component; use clustering alone where available and keep regional levels on the advisory cards.** If no clustering tier is available, the overall value is null. Unresolved compound documents do not become guessed country scores. The highest-regional-level preview remains a comparison experiment; the production publisher accepts only exclusion.

## Read-only comparison

```sh
uv run --frozen python db/scripts/preview_official_scores.py --output .local/v2/official-scoring/comparison.json
```

This uses only the restricted hosted reader and a repeatable-read, read-only transaction. It records country catalogue, old published components, currently displayed official US versions, an input checksum, source/retrieval dates, both regional-policy previews, coverage, conflicts and per-country changes. It has no write flag and performs no permission, schema, model or score changes. Existing output paths are not overwritten. After the policy decision, use `--regional-policy exclude` or `--regional-policy highest` for a single-policy report.

## Scoped publication and rollout order

Migration `0009` adds official level, normalized components, formula, publication run ID and publication timestamp to scores. Existing numeric values and model input columns are unchanged by migration. A private RLS-protected official history table stores each published country's full source references; the run ledger stores the exact input snapshot and checksum, including previous score metadata. Do not store official levels in `bert_score`.

The dedicated `safetrip_score_publisher` starts NOLOGIN. It receives only column-level INSERT/UPDATE grants for publication outputs, SELECT on the reviewed input projections, append-only history access, and run-ledger access restricted by RLS to `publish-official-scores`. It cannot update BERT/clustering columns, read the raw advisory schema, delete scores, or change earlier ingestion runs. The ingestion writer's privileges are unchanged. Keep publisher credentials local/backend-only, never in Vercel or NEXT_PUBLIC settings.

The publisher uses a serializable transaction and the same advisory locks as ingestion. It re-reads and fingerprints current inputs, independently recalculates all outputs, checks the saved preview exactly, rejects conflicts, and commits score rows, per-country history and successful run status together. Failures preserve a failed attempt record while score/history writes roll back. A preview cannot be reused after a successful publication because publication metadata is part of the input snapshot. Serialization failures require a fresh read/review as appropriate, not blind retries.

1. Apply the additive hosted script as `postgres` in Supabase SQL Editor:

```sh
pbcopy < db/hosted/003_official_scores.sql
```

This requires the earlier hosted 002 migration. Do not run the local Alembic chain on Supabase. The standalone script creates the NOLOGIN role, fields and policies in one transaction and intentionally fails on an unexpected existing install.

2. Merge/deploy the scoring UI before publishing. It reads the new metadata via the already configured restricted PostgreSQL reader, alongside legacy Supabase country/culture reads. Optional JSON projections support the old schema during staged rollout. New-format scores show Official US advisory and normalized Clustering component; historical BERT predictions are retained but excluded from the breakdown. A failed/unknown methodology read is labelled unavailable rather than BERT. Level 4 is prominently visible outside the collapsed breakdown.

Verify `https://safetripiq.vercel.app/api/scoring-status` reports `supported_formula: us-official-cluster-v1`, `regional_policy: exclude`, `schema_ready: true`; before first publication, `published_rows` should be zero. No additional Vercel environment variables are needed.

3. Set up/check the publisher, then generate a fresh single-policy preview:

```sh
uv run --frozen python db/scripts/publish_official_scores.py setup
uv run --frozen python db/scripts/publish_official_scores.py check
uv run --frozen python db/scripts/preview_official_scores.py --regional-policy exclude --output .local/v2/official-scoring/approved.json
```

4. After reviewing the preview, explicitly publish:

```sh
uv run --frozen python db/scripts/publish_official_scores.py publish --preview .local/v2/official-scoring/approved.json --output .local/v2/official-scoring/published.json --site https://safetripiq.vercel.app --write
```

The helper checks the public production readiness endpoint before attempting writes. Use new output paths; an empty artifact is not a commit marker. If an error occurs, inspect the printed attempt run ID in the run ledger before retrying; an ambiguous client response must not be mistaken for a rollback.

5. Verify readiness reports 250 published rows (including null overall scores), 215 non-null values under the verified snapshot, source/date provenance, and correct breakdown labels. CAN/JPN should stay 10.0 and USA 6.0; PSE and BES should have no overall score while regional warnings remain visible. Compare against the saved preview and confirm BERT/clustering inputs remain unchanged. A later data refresh may change those counts; the approved input checksum, not hardcoded country counts, controls publication.

The successful run's `input_payload` preserves prior numeric values and methodology fields for a reviewed restore if needed. No automatic downgrade/restore command is provided: do not delete history or re-run legacy publication to change official scores. Disable the publisher login and prepare a targeted restore transaction if post-publication review finds an issue. Transaction-failure rollback is tested separately from a deliberate post-publication restore.

No new sources, clustering retraining, BERT inference or AWS resource changes are required for this scoring preview.

For subsequent manual source refreshes and optional score publication through GitHub Actions, see [the refresh workflow guide](advisory-refresh-actions.md). That workflow reuses these scoped accounts and preview/publication checks; it does not enable a schedule.

## Verified read-only preview — November 5, 2026

Across 250 hosted catalogue entries, excluding regional-only US advisories yields 165 countries with both components, 47 with US advice alone, three with clustering alone, and 35 with neither. Thirty-one country scores would change. Canada and Japan remain 10.0; USA remains 6.0. There are no conflicting whole-country levels; Tonga's two whole-country documents agree and contribute one US component.

The user chose regional exclusion. Palestine and BES have no published clustering tier, so their overall values are null and their regional advisory cards remain visible. The earlier comparison artifact predates the BES scope correction; `approved-exclude-v2.json` is the updated preview. Four countries gain scores, while BES loses its prior overall score because that national component relied on incorrectly classified regional coverage; the others are numeric changes.

Evidence is stored only under ignored `.local/v2/official-scoring/comparison.json` and the fresh single-policy preview, including the source input snapshots/checksums. Preview commands made no database writes. Publication, migration and UI code are implemented locally; no production scoring schema or score values have been changed by this implementation task.

Local verification passed 106 dependency-free unit tests, 49 PostgreSQL integration tests, 12 frontend tests and seven real PostgreSQL website-query tests. The hosted-style disposable rehearsal applied the scoring bridge and published with the restricted role. Tests cover actual source changes after preview, edited results, stale reuse, mid-write rollback, history/provenance, denied model-input writes, single-component labels, Level 4 visibility and methodology failure handling. Lint has three pre-existing image warnings; typecheck passed. A read-only hosted prerequisite check confirmed the affected-area migration is installed and the scoring migration is not yet installed.

## BES source-scope correction

Final review found that the US document titled Saba and Sint Eustatius had been classified as whole-country coverage for BES, although BES also includes Bonaire. Parser `us-uk-ingestion-v3` now shares the explicit regional-name catalogue with the country resolver and marks this document regional. The singleton Sint Eustatius alias is also regional. This fixes source geography without inferring a national warning.

A fresh BES-only capture contained two US documents and one UK document. Its explicit subset preflight reported no missing country keys or missing prior documents in that selected scope. Re-ingestion appended three v3 source versions, created no new documents, and preserved the prior history. Read-only verification confirmed US coverage of Bonaire and Saba/Sint Eustatius as two `parts` records, with the UK group document still whole-country. Public score values were unchanged by the correction; the new scoring preview withdraws the unsupported BES national value under the chosen policy.

The hosted operator helper now supports explicit bounded subsets (`--iso3`, repeated as needed) only when capture selection and a pinned preflight plan agree. Subset gap reporting is limited to the selected countries; unselected destinations are not treated as missing. Full-world mode still requires its explicit flag and plan. Generated correction evidence stays ignored under `.local/v2/bes-scope-correction/`.

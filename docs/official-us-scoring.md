# Official US advisory plus existing clustering

Scope decision: defer new external indicators and new NLP scoring. Replace the BERT input in the legacy composite with the actual US advisory level, preserving the existing conversions and equal weights as an application policy. UK warnings remain a separate source-backed display; BERT remains experimental.

## Preview formula

- US level 1–4 becomes `10 - 2.5 * (level - 1)`: 10, 7.5, 5, 2.5.
- Existing published clustering tier 0–4 keeps `10 - 2 * tier`: 10, 8, 6, 4, 2.
- Two components are averaged equally. One available component is used alone and labelled accordingly. Neither available produces null, never an imputed safe score.
- Formula `us-official-cluster-v1` records the regional policy separately. These are ordinal-to-display conversions, not probabilities of harm or a statistically calibrated travel-safety scale. Level 4 remains explicitly flagged; no numerical cap has been silently introduced.

The clustering inputs come from existing published `scores.clustering_score`, not a fresh K-means fit or arbitrary raw cluster IDs. Comparison of the pre-migration snapshot found all 168 published clustering values equal to the corresponding stored clustering values. This preserves the existing asserted risk-tier interpretation; it does not independently validate the original manual tier ordering or data vintage.

For multiple mapped whole-country US documents, equal levels can contribute one component while all source documents remain in the report. Disagreeing levels are flagged for review and do not silently choose a winner. Regional US documents remain individually traceable. The preview supports comparing exclusion from the countrywide component versus explicitly choosing the highest regional level; the final regional policy must be settled before publication. Unresolved compound documents do not become guessed country scores.

## Read-only comparison

```sh
uv run --frozen python db/scripts/preview_official_scores.py --output .local/v2/official-scoring/comparison.json
```

This uses only the restricted hosted reader and a repeatable-read, read-only transaction. It records country catalogue, old published components, currently displayed official US versions, an input checksum, source/retrieval dates, both regional-policy previews, coverage, conflicts and per-country changes. It has no write flag and performs no permission, schema, model or score changes. Existing output paths are not overwritten. After the policy decision, use `--regional-policy exclude` or `--regional-policy highest` for a single-policy report.

## Publication is a later explicit step

Before changing production, inspect the full preview, settle regional/conflict rules and confirm use of the frozen clustering tiers. Then add explicitly named official-advisory fields, formula/input provenance and a narrowly scoped publication path with atomic history and rollback. The existing ingestion writer intentionally cannot update public scores; do not grant it broad score access to bypass this separation. Update the public breakdown to say Official US advisory, preserve experimental BERT history separately, and verify before/after values on a local rehearsal. Publish only after the data and UI contracts are ready together.

No new sources, clustering retraining, BERT inference or AWS resource changes are required for this scoring preview.

## Verified read-only preview — November 5, 2026

Across 250 hosted catalogue entries, excluding regional-only US advisories yields 165 countries with both components, 48 with US advice alone, three with clustering alone, and 34 with neither. Thirty country scores would change. Canada and Japan remain 10.0; USA remains 6.0. There are no conflicting whole-country levels; Tonga's two whole-country documents agree and contribute one US component.

The highest-regional-level variant changes only Palestine in this snapshot: it has no published clustering tier, so its combined value changes from null under exclusion to 2.5 using its highest regional level of 4. This does not mean the source publishes a Palestine-wide US level; it is an explicit proposed aggregation policy. The final policy is awaiting the user's decision. All original regional records remain in the preview.

Evidence is stored only under ignored `.local/v2/official-scoring/comparison.json`, including the source input snapshot and checksum. The command made no database writes. The preview is implemented and tested; production schema, score publication and public breakdown labels have not been changed.

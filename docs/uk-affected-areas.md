# Official UK affected-area excerpts

The regional flags identify the presence of restrictions; they do not enumerate geographic areas. The existing stored GOV.UK JSON contains the official warnings-and-insurance HTML, and the paragraph table already retains its text and headings.

The versioned `uk-warning-areas-v1` extractor selects explicit FCDO warning blocks from that section. It keeps complete paragraphs and list items until the next heading boundary, including distances, exceptions, access routes and surrounding context. It handles nested area headings and sibling headings whose text explicitly states a present-tense FCDO restriction. It does not turn arbitrary regional-risk headings, historical advice, or closed borders into travel restrictions, infer severity, draw polygons, or call a language model. If no recognized block exists, the UI points to the full source rather than inventing a list.

Migration `0008` adds one private append-only reference table with a foreign key to the exact stored paragraph. A restricted owner-rights display view exposes only references for the active extractor and the currently displayed UK version, where a regional flag is present. The reader still cannot access raw versions or the paragraph table. Hosted SQL explicitly removes Supabase default API grants. Existing public scores and source versions are unchanged.

The API returns optional `warning_excerpts` with source paragraph identifiers, source headings and plain text. The UK card shows an expandable **Affected areas** section. Text is escaped by React; source HTML is never rendered directly. Unknown, missing or failed excerpt data has an explicit source-link fallback, and an optional excerpt query failure does not hide the official warning cards. The existing official link and source/retrieval dates apply to the same version. Some advice includes neighbouring-area context; the display does not claim every place mentioned has the same restriction.

Future ingestion maintains references for both new and reused UK versions in the existing transaction. An extractor output cannot silently change under the same version. Existing stored versions are populated by a separate, repeatable backfill that checks text and headings against the stored paragraph identifiers before inserting anything.

## Verification

The November 5 hosted read-only preview examined all 57 stored regional-warning versions and matched all 57, identifying 604 source paragraph references with no fallback cases. No production excerpt rows or schema changes were made by this preview. Source layouts may change; this snapshot does not guarantee future extraction coverage. Unit tests cover boundary handling, lists/exceptions, negated/historical statements, unsupported-layout fallback and provenance mismatches. Database tests cover visibility, read-only projection, replay and replacement by a newer source version.

## Hosted rollout

Do not run the local Alembic chain against hosted Supabase. The standalone additive script is generated from the same reviewed DDL:

```sh
.local/database-venv/bin/python db/scripts/build_warning_areas.py
pbcopy < db/hosted/002_uk_warning_areas.sql
```

Run the copied SQL in Supabase SQL Editor as `postgres`. It creates only the private reference table, policies and restricted view. It runs in a transaction and intentionally fails if already installed; do not disable errors or add IF NOT EXISTS to bypass unexpected state. Keep exposed schemas as `public` and `graphql_public`.

Then populate the references using the existing restricted writer:

```sh
uv run --frozen python db/scripts/backfill_warning_areas.py --output .local/v2/uk-warning-areas/committed.json --write
uv run --frozen python db/scripts/hosted_reader.py check
```

The default backfill without `--write` is read-only; it can run before the new schema is installed. Existing result files are not overwritten. A write reuses existing matching references; it creates no model predictions, source versions, fetch observations, or public scores. It shares the ingestion transaction lock to avoid concurrent backfills/imports.

After checks pass, merge the extension PR and redeploy `safe-trip-iq-ew9z`, the project serving `https://safetripiq.vercel.app/`. No additional environment variables are needed. Verify ARM, AGO and THA for area lists, and CAN for the no-regional-warning case. Do not rename or expose reader credentials. The original advisory cards still work if the optional excerpt view is unavailable.

## Remaining V2 work

Official US/UK ingestion, hosted storage, full-world import and basic production display already work. This extension still needs the hosted migration, backfill, merge/deploy and live checks above. Separately, the new scoring formula and missing-component rules need a decision and versioned implementation; NLP topic/context extraction needs labels and independent evaluation before promotion; scheduled refreshes need deployment, monitoring and raw-capture retention appropriate to the storage budget; and the deferred research/repository cleanup and final architecture documentation remain. BERT and automated AWS scheduling are not prerequisites for showing these official area excerpts.

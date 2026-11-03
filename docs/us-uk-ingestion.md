# V2 US/UK advisory ingestion

Two model-free commands connect source capture to the private schema introduced in migration `0006`:

```text
capture-advisories -> complete raw-response bundle -> ingest-advisories preview
                                                 -> --write -> private document/version history
```

Public scores, the legacy advisory tables, and public refresh status are not updated by this path. AWS publishing/scheduling and hosted Supabase migration remain deferred.

## Local setup

From the repository root, start/migrate the fixed local database:

```sh
bash scripts/setup_local_db.sh
```

The local seed contains CAN, JPN, and USA. The examples below use those destinations. A wider import requires a complete country catalogue; ingestion rejects missing foreign-key targets rather than creating guessed countries. Grouped/unmapped destination coverage is retained explicitly as unresolved.

## Capture and preview

```sh
uv run --frozen safetrip capture-advisories \
  --iso3 CAN --iso3 JPN --iso3 USA \
  --output .local/v2/capture-001.json

uv run --frozen safetrip ingest-advisories \
  --input .local/v2/capture-001.json \
  --output .local/v2/preview-001.json
```

Capture fetches the UK index, the US feed, and the selected UK destination documents. Requests use a one-second pause, bounded retries, timeouts, official HTTPS endpoints, and no cross-host redirects. Use `--all` instead of `--iso3 ...` to collect the full destination index; this makes hundreds of requests and produces a larger local bundle.

The self-contained JSON bundle preserves exact source-response bytes as base64, SHA-256 hashes, URLs, and actual retrieval timestamps. It is source data, not a credential file, but generated bundles/results belong under ignored `.local/`, not Git. Capture does not load `.env`, access a database, or load a model.

Partial bundles remain marked incomplete and cannot be ingested. A capture can be complete at the HTTP layer but fail normalization because of a new schema/status/mapping; the source responses remain available for inspection.

Preview validates source hashes, dates, identity/index agreement, expected UK responses, US title levels, warning flags, coverage, and paragraphs without database access. It reports per-country/source availability and review cases. Source absence is `not_in_capture`, not a reassuring warning, a predicted score, or proof that a source withdrew its advice. The USA legitimately has UK advice without an equivalent US foreign-travel page.

## Write to the local database

These credentials are fixed local Docker fixtures, not production secrets:

```sh
SAFETRIP_DB_BACKEND=postgres \
SAFETRIP_DATABASE_URL=postgresql+psycopg://safetrip_writer:writer_local_only@127.0.0.1:55432/safetrip \
uv run --frozen safetrip ingest-advisories \
  --input .local/v2/capture-001.json \
  --output .local/v2/ingested-001.json --write
```

The command explicitly requires the Postgres backend and restricted writer. It cannot fall back to a Supabase service-role client. Do not point it at hosted Supabase until the schema/role migration has been checked and applied there.

An existing output path is rejected before database work. On success, the result includes a run ID and new/reused version counts. A failed run can leave an empty or partial output file; file existence does not establish success. The run ledger and the command's exit status are authoritative.

## Storage behavior

- Document identity is `(source, native source key)`: US GUID/canonical link and UK content ID. ISO3 is a coverage join key, not a shared document ID.
- All documents in a batch are committed atomically under the existing advisory locks. Unknown country-catalogue entries stop the write before document inserts.
- A version is identified by document, raw-content hash, and parser version. Replaying identical input reuses the version and adds an observation in a new run. The original capture timestamp is preserved; replay is not a new live fetch.
- Changed source content creates another version; old paragraphs/evidence remain addressable. A stored normalization fingerprint rejects changed parser output under an unchanged parser version.
- New paragraphs preserve headings and source text. This is source extraction, not a completed NLP input-cleaning/annotation stage. No topic model, severity model, or combined score runs during ingestion.
- US source-item XML is serialized for document-level version hashes. The exact original full feed and all UK responses are retained once per run in `public.raw_feeds` as the capture-bundle JSON bytes, with the format identified by the run command/metadata. This table remains private.
- Raw capture and run failure survive a normalization/transaction failure; normalized documents and successful run status commit together. No public score publication or freshness update is implied by ingestion success.
- Multiple distinct US documents for one country are retained and flagged in `overlapping_country_documents`; no arbitrary winner is selected. Duplicate native identities within a capture are rejected.
- Regional and grouped advice remains distinct. Known compound UK destinations and composite US destinations require coverage review. A document covering a country is not equivalent to an official warning applying to every part of it.

Before hosted rollout, define raw-capture/history retention and measure storage growth. Full UK pages include long change histories; replaying every full capture indefinitely is not a storage-retention policy. Incremental HTTP fetching and approved public summaries remain later work.

## Verification

```sh
uv run --frozen python -m unittest discover -s tests -q
bash scripts/check_database.sh
```

Tests cover source-specific levels/flags, one-source coverage, capture corruption/incompleteness, duplicate identities, compound destinations, official URL boundaries, model-free previews/container entrypoint, repeat ingestion, source changes, parser-version reuse, exact paragraph provenance, and deliberate mid-batch rollback. Integration checks target only the fixed local Docker database.

The synthetic offline capture fixture is `tests/fixtures/us_uk_capture.json`. It has a complete two-destination index/feed pair, dates, and public example source URLs. It is not a live government dataset or independent NLP evaluation set.

## Current next steps

Connect approved source comparison queries/UI, decide canonical/region publication policy, audit the hosted schema, and migrate Supabase safely. NLP context/severity annotation and independent evaluation remain separate requirements. Keep using V2 ingestion commands for source storage; legacy `refresh` still denotes the earlier BERT workflow.

## Verified milestone — November 3, 2026

- Live subset: five documents (two US, three UK) for CAN/JPN/USA ingested into local Docker Postgres. Replaying the same capture created zero documents/versions and reused all five versions, while retaining original retrieval times.
- Full read-only capture: 228 source responses (UK index, US feed, 226 UK pages); preview normalized 218 US advisories and 226 UK documents. It reported six review-required records: four unresolved compound destinations and two records in one overlapping country-document group. No full-world database import was performed.
- 86 unit tests and 41 local database integration tests passed. Mid-batch rollback retained raw capture and a failed run without partial normalized writes; parser drift under the same version was rejected. The original public-score baseline remains unchanged.
- A secret scan of the implementation files found no leaks. Generated source captures/results remain ignored under `.local/`. Hosted Supabase, AWS, public scores, and NLP models were not changed.

# PRD: US/UK advisory intelligence

**Project:** SafeTrip IQ · **Date:** October 14, 2026 · **Status:** Implementation brief

## Problem and goal

SafeTrip IQ currently stores a single advisory/prediction per country. Its US advisory-level classifier has demonstrated transfer failures, while a read-only pilot confirms that US and UK advice can be collected, matched, and inspected together.

Build a reliable, source-backed advisory pipeline with a meaningful NLP capability: extract destination-specific threats and their evidence from both governments' text. Keep official warnings distinct from model interpretations. A combined NLP index is a later, evaluation-gated output; adding another source does not establish score accuracy.

## First release

Users can open a destination and see US and UK advice side by side, including official warning levels/statuses, regional coverage, source links, update dates, and missing/stale data. The existing clustering component remains available.

Production scoring uses the official US advisory component and clustering under an explicit versioned application formula. UK flags remain separately visible until a cross-source aggregation policy is defined. Experimental NLP results cannot affect the production composite. Any displayed experimental evidence must be labeled accordingly and link to its supporting source passage.

This release includes source ingestion, versioned storage, publication, focused frontend changes, weekly operation, and repository cleanup. Full frontend redesign, clustering retraining, database-provider migration, and a production NLP score are outside its initial scope.

## Functional requirements

- Collect US RSS and the official GOV.UK Content API with timeouts, bounded retries, low request rates, and immutable raw snapshots.
- Preserve source identity, original title, URL, retrieval time, source update/review dates, content hash, and parser version. Snapshot dates and change notes must not be mistaken for original publication dates or historical bodies.
- Map source destinations to ISO3 and explicit geographic coverage. Support one document covering multiple territories. Keep whole-country and regional warnings separate; never silently apply a regional warning to the whole country.
- Parse US levels from titles and retain UK warning flags without pretending the two systems are equivalent. Unknown mappings/statuses and conflicting same-date documents require review before publication.
- Retain document versions and selected risk sections with headings and paragraph references. Reanalyse only when relevant text or the analysis version changes.
- Publish verified results atomically with run history and score provenance. Repeated runs are idempotent. Failures preserve the last verified publication and mark freshness appropriately. Confirmed missing/withdrawn advice stays blank; a clustering-only destination remains valid.
- Present each source independently, including disagreement and unverified coverage. No source failure may silently become a reassuring warning or score.

## Data and architecture

Keep Supabase/Postgres, Vercel, Docker, GitHub Actions, and the scheduled Fargate worker design.

Extend advisory storage into:

1. **Documents and coverage:** source/document identity, canonical URL, country/region associations.
2. **Document versions:** raw content, official metadata, extracted sections, hashes, and source dates.
3. **NLP analyses/evidence:** versioned topic, context, scope, severity where evaluated, supporting paragraph references, and review status.
4. **Published summaries:** explicitly named official advisory fields, clustering, formula version, freshness, and approved display data.

Reuse existing run/publication history and transactional safeguards. Keep raw/experimental records private through explicit grants and RLS; expose only intended published fields to read-only website access. Do not repurpose `bert_score` to store official levels.

Use additive local migrations first. Before hosted migration, compare the actual Supabase schema, take a recoverable backup, test the upgrade and rollback path, and verify public reads and restricted writes. Retire the legacy path only after cutover is verified.

## NLP scope and evaluation gate

Initial categories: crime, kidnapping, terrorism, conflict/unrest, health, natural hazards, transport, and legal restrictions. Separate topic mentions from destination-specific risk, generic advice, historical events, third-region effects, negation, and geographic scope.

Define the annotation/severity rubric and quantitative acceptance thresholds before training or selecting a model. Create a new independently reviewed evaluation set with verified provenance; group related US/UK documents and destination revisions together. Previously consumed US evaluation and the developer-reviewed 47-paragraph pilot cannot serve as independent promotion evidence.

Compare cheap baselines before BERT training. Report per-source/category precision and recall, severe-risk misses, scope/context errors, and evidence traceability. No combined NLP score is promoted until both extraction and the proposed aggregation behavior pass their preregistered criteria.

## Delivery and acceptance

| Milestone | Acceptance |
| --- | --- |
| 1. Schema and contracts | Additive migration and permissions pass local integration checks; explicit source/version/coverage records work. |
| 2. Ingestion | Full-source preview reports coverage, review cases, provenance, and failures; reruns do not duplicate versions. |
| 3. Publication and UI | Source comparisons, missingness, history, rollback, and score separation pass; one controlled hosted refresh is verified. |
| 4. Weekly operation | One scheduled 1 vCPU/2 GiB task completes and stops; failure alerts/freshness work; actual usage is checked against the existing budget. |
| 5. Lean repository | Fresh clone runs locally and passes CI; obsolete paths/duplicate data removed after dependency checks; historical evidence preserved with retrieval manifests. |
| Later: NLP promotion | New independent evaluation meets thresholds fixed before tuning; aggregation is documented, versioned, and reviewed. |

## Cleanup requirement

Keep production code, migrations, meaningful tests, and concise product/architecture/operations documentation. Consolidate research under one directory and historical reports into an archive or external artifact location. Keep generated snapshots, datasets, and model weights out of normal source commits. Preserve the frozen baseline and useful experiment evidence before deleting anything. Cleanup is part of feature completion, not an indefinite follow-up.

## Decisions before affected work

- Country-level presentation of separate regional warnings and conflicting canonical records.
- Official advisory-to-display conversion and any future US/UK/NLP aggregation weights.
- Severity rubric, annotation protocol, and numerical NLP promotion thresholds.

These decisions do not block source storage and read-only collection. Hosted cutover follows verified migration, permission, and publication checks.

## Evidence

[US/UK feasibility pilot](us-uk-pilot-results.md) · [Label and transfer audit](label-transfer-audit.md) · [UK API investigation](uk-travel-advice-investigation.md)

## Checkpoint — November 3, 2026

AWS image publishing and weekly scheduling are deferred; no account upgrade is required for the next local milestones. OIDC/publishing code is prepared but has not been applied to AWS.

Migration `0006` adds a private `advisory` schema with source documents, immutable versions, coverage, fetch observations, paragraphs, analyses, and evidence references. Local tests verify isolation, source-specific official warnings, deduplication, history, and evidence provenance. Existing public scores and hosted Supabase are unchanged.

Next: connect the source adapters to this storage with transactional, repeatable ingestion; then build the source comparison queries/UI. The existing pilot is read-only and is not yet the production ingestion path. Repository consolidation remains a feature-completion requirement.

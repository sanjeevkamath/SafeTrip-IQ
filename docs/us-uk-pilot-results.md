# US/UK NLP feasibility pilot — October 13, 2026

## Decision

**Proceed with source integration and an experimental evidence-extraction pipeline. Do not promote a combined NLP safety score yet.** The integration works on the tested sample; a cheap lexical NLP prototype extracts useful topic evidence. No learned-model risk/severity performance or numerical-score validity has been established.

This can be an incremental change to SafeTrip IQ. Docker, the scheduled-worker design, Postgres transactions/history, CI, Vercel, and the clustering component can be reused. The advisory storage/scoring contract needs a deliberate extension; the whole application does not need to be rebuilt.

## What was actually tested

- Read-only normalization of 12 US and 12 UK documents for France, Thailand, Afghanistan, India, Ukraine, Japan, Canada, Mexico, Kenya, Nigeria, Türkiye, and South Africa.
- A live US feed request, seven additional UK requests, and five preserved UK probe snapshots. Collection mode and raw-content hashes are recorded.
- ISO3 pairing, UK warning flags with whole-country/partial scope, source URLs, destination update fields, selected sections, headings, and paragraph extraction.
- 2,327 extracted paragraphs across 24 documents. UK entry requirements and getting-help sections are excluded from this pilot's risk text; UK safety/security, health, regional risks, and warnings/insurance are retained.
- The destination-index mapping audit now accounts for all 226 index entries: 223 have a single primary ISO mapping, while three grouped destinations explicitly require mapping review. This is an identity crosswalk, not proof that a page's every territorial reference applies uniformly to that ISO.
- A reproducible 47-paragraph sample (seed 42, up to two paragraphs per document), reviewed against an eight-category topic rubric before generating prototype predictions.

Raw JSON/XML, manifests, topic annotations, evidence, evaluation, and a local HTML preview are saved in ignored `.local/research/us-uk-pilot-v1/`. No production data, AWS deployment, existing scores, clustering model, or trained BERT checkpoint was modified.

## Prototype results

The prototype is a **rules/lexicon topic extractor**, not BERT or a newly trained statistical model. It uses paragraph text and heading context and returns source-linked evidence plus review flags. The eight topics are crime, kidnapping, terrorism, conflict/unrest, health, natural hazards, transport, and legal restrictions. Detecting a topic does not establish active danger or severity.

| Sample | Paragraphs | Exact agreement on the complete topic set | Topic micro-precision | Topic micro-recall |
| --- | ---: | ---: | ---: | ---: |
| US | 23 | 86.96% | 93.94% | 93.94% |
| UK | 24 | 95.83% | 96.15% | 100.00% |
| Combined | 47 | 91.49% (43/47) | 94.92% | 96.55% |

These are **developer-reviewed feasibility diagnostics**. The rubric/rules may have been influenced by inspected pilot content, annotation was performed by one assistant/developer review, the destinations were deliberately selected, and this is not an independent generalization benchmark. Neither these percentages nor the 1,287 automatically tagged evidence paragraphs validate a safety score. The extraction itself took milliseconds; collection/normalization and any future ML inference are separate costs.

Observed errors include:

- A driver/road mention in a kidnapping passage produced a transport topic, while the word “rob” was missed as crime.
- A paragraph describing criminals posing as airport greeters added a transport topic where the reviewer labeled crime only.
- Extortion by captors was recognized as kidnapping but missed as crime.
- Arrest risks during unapproved protests added conflict/unrest, exposing an ambiguous category boundary in the rubric.

The original evaluation is preserved. The baseline has not been tuned and rescored against these errors.

## Why a numerical score is not ready

There are **20 UK paragraph texts repeated identically across at least six pilot destinations**. One global terrorism warning and its linked general guidance occur in all 12. General healthcare/insurance advice also repeats widely. Treating these as destination-specific risk evidence would inflate scores across the board.

Some passages describe past events, third-country travel disruption, generic precautions, or government-employee restrictions. The current extractor can flag a few obvious contexts, but it has no validated geography, negation, severity, or affected-traveller classifier. UK partial-country flags and US regional warnings must not be collapsed into a single global country level automatically.

The existing US advisory-level BERT remains unsuitable for this different task without new labels and evaluation. Adding UK documents supplies useful text and provenance; it does not automatically resolve the earlier transfer failure.

## Architecture changes needed

1. **Source records:** extend advisory storage from one row per country to country/region + source + stable document identity + version. Preserve raw content, source dates, official flags/levels, and extracted sections. Existing run IDs/history and restricted writers can be reused.
2. **Experimental NLP records:** store category evidence, paragraph references, context/scope, model or rules version, and review status separately from official warnings. Keep official US and UK signals visible individually.
3. **Aggregation contract:** define a versioned experimental rule for combining evidence, source disagreement, freshness, regional scope, and clustering. Never treat repeated wording or two governmental reports as independent incident probabilities. Keep the composite out of production until its inputs and behavior are validated.
4. **Worker/UI:** add the UK adapter and incremental section hashing to the current worker; expose source comparisons and evidence in the frontend. No new always-on service is required for this architecture.

## Recommended next implementation

Implement the source-record migration, explicit territory/duplicate policies, and read-only comparison UI first. In parallel, create a new annotation set with paragraph labels for topic, destination-specific versus generic/historical context, severity, and geographic scope. Use separate reviewers where possible and a new independent evaluation cohort fixed before tuning. Group related US/UK documents and versions of the same destination together; the current US feed may overlap the already consumed evaluation, and five UK pages were previously inspected.

Only then compare a cheap statistical or pretrained NLP model with this baseline. Promotion criteria should cover per-source topic precision/recall, high-severity misses, geographic/context mistakes, evidence traceability, and the proposed aggregation behavior. Until those gates pass, official advisories and clustering can serve production while the combined NLP index remains experimental.

## Commands

```sh
uv run --frozen python -m scripts.run_us_uk_pilot
uv run --frozen python -m scripts.evaluate_us_uk_pilot
uv run --frozen python -m unittest discover -s tests -q
```

Collection and evaluation refuse existing artifacts. The topic annotations are a reviewed artifact in the pilot directory, not automatically generated ground truth; evaluation requires them. Existing snapshots/reports should be inspected rather than overwritten. The normalization module does not fetch content, load credentials, publish records, or calculate a safety score.

Verification: 71 unit tests pass, including HTML extraction, unknown-warning rejection, partial-scope preservation, and grouped-territory handling. No database logic changed, so the previously passed 30 integration tests were not rerun solely for this read-only module.

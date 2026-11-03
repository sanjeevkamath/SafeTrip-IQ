# Label, cleaning, and transfer audit — October 13, 2026

Production direction: use the official State Department advisory level alongside the clustering component. BERT remains experimental. No new BERT training, dataset rebuild, fresh-feed model predictions, AWS deployment, or production database writes were performed in this audit.

## What the existing validation results show

Logistic regression achieved **29/32 = 90.63% Level 3 recall** on historical validation, then **10/26 = 38.46%** on the consumed fresh feed. Level 3 was not uniformly difficult for every model. BERT's weakness and logistic regression's transfer failure must be distinguished.

The following breakdown reuses the saved validation predictions, with their original best-epoch/model choices. COVID membership is a lexical mention of `covid` or `coronavirus`, not a verified era or labeling regime. Even an update note saying obsolete COVID links were removed qualifies.

| Existing model | COVID mentions: accuracy (47 rows) | No COVID mentions: accuracy (103 rows) | COVID Level 3 recall (17 rows) | No-COVID Level 3 recall (15 rows) |
| --- | ---: | ---: | ---: | ---: |
| Logistic regression | 82.98% | 91.26% | 88.24% | 93.33% |
| Full-document BERT | 65.96% | 80.58% | 47.06% | 33.33% |

Class counts for Levels 1–4 are 4/10/17/16 in the COVID subset and 24/51/15/13 in the other subset. Raw accuracy is therefore not a controlled comparison across these groups. The logistic results nevertheless show that historical non-COVID examples were already recognized well; COVID absence alone cannot explain the fresh-feed failure.

## Label consistency and cleaning

Every source reference behind the frozen training and validation rows retains its original CSV label correctly (1–4 mapped to class IDs 0–3). Among 1,057 training source references, a first-recommendation screen found 1,031 agreements, 12 apparent disagreements, and 14 unresolved cases. Among 238 validation references, it found 231 agreements, 6 apparent disagreements, and 1 unresolved case. These counts include duplicate source references, not independent documents.

Manual inspection shows many disagreements come from update notes mentioning “Do Not Travel areas” before an overall “Exercise increased caution” recommendation, or regional warnings in a low-level country advisory. Do not relabel these automatically. Mauritania is a specific unresolved example: frozen training CSV row 403 and original test CSV row 71 have label 3, while their body begins “Exercise increased caution.” Both match two entries in `old_advisories_minimal_no_merge.csv` labeled 3. This establishes an inherited body/label inconsistency, not whether the source title, source body, or an earlier join was wrong. An original dated advisory is needed to settle it.

The frozen v3 dataset retains three singular recommendation phrases in training. Current v4 removes them and the known Korea/DRC/DPRK aliases. No validation recommendation residues were found by the targeted screen. A negative regex screen does not establish that every indirect label or geographic clue is gone.

## Cheap validation-only ablations

These are diagnostic interventions, not candidate production cleaners. All use the same C=10, seed, vectorizer settings, class balancing, and frozen validation set. No fresh predictions or parameter search were performed. The control reproduces the saved predictions exactly.

| Intervention | Accuracy | Macro-F1 | Level 3 recall |
| --- | ---: | ---: | ---: |
| Frozen v3 control | 88.67% | 0.8940 | 90.63% |
| v4 cleaning only | 88.67% | 0.8940 | 90.63% |
| Remove COVID/CDC sentences from both splits | 83.33% | 0.8359 | 78.13% |
| Remove qualitative severity phrases | 88.67% | 0.8920 | 90.63% |
| Remove selected generic advice sentences | 88.00% | 0.8855 | 87.50% |
| Train only on no-COVID-mention rows (435 examples) | 83.33% | 0.8324 | 65.63% |

Training only on the no-COVID subset changes both sample count and class distribution, so it does not isolate the effect of the labeling regime. Its no-COVID validation accuracy was 93.20%, versus control 91.26%: just two additional correct examples. Its COVID-subset accuracy fell to 61.70%. This is insufficient evidence to choose a new training policy.

Removing COVID/CDC sentences creates two empty training documents; removing selected generic advice creates one. The diagnostic classifier includes these rows (zero text features after vectorization); these interventions must not be adopted as production cleaners. Sentence regexes can also remove useful evidence. The v4 cleaning-only intervention produces no empty rows and identical validation predictions to control.

## Source dates and the labeling-regime hypothesis

Exact matching after the documented legacy JSON-to-CSV normalization links **1,521 of 1,609 original rows** to repository intermediate CSVs or the raw title/body capture. No label disagreements were found among these exact lineage matches. Ninety source rows match the title/body capture, recovering named-country metadata for those references. None of these files preserves a per-row publication timestamp.

The legacy JSON exporter deletes digits and many non-ASCII characters. This damages date and numerical-risk evidence; configured Wayback capture URLs cannot restore individual publication dates automatically. Another archived export helper excludes every Level 1 body that starts with “Exercise normal precautions,” regardless of whether later risk content is substantial. That is a selection-bias hazard; we have not established which output files were generated by that particular helper.

The previously downloaded raw RSS snapshots do preserve publication dates:

| Snapshot file | Publication years in its items |
| --- | --- |
| 2019 | 2018: 78; 2019: 131 |
| 2021 | 2019: 1; 2021: 212 |
| 2024 | 2023: 164; 2024: 48 |
| Current downloaded feed | 2023: 3; 2024: 9; 2025: 40; 2026: 171 |

These are counts over the complete raw feeds, not the filtered 179-document evaluation cohort. A snapshot date is not the publication date of every document. The current feed is not a strict future-period holdout relative to the undated CSVs. Prior matching of these three archives produced no exact matches under the then-used cleaned representation; similarity matches must not be upgraded into verified dates.

A real policy change is independently documented: the [State Department's April 19, 2021 FAQ](https://travel.state.gov/content/dam/NEWTravelAssets/pdfs/Travel%20Advisory%20Update%20-%20%20Frequently%20Asked%20Questions_.pdf) describes giving greater weight to CDC assessments and distinguishes CDC health notices from State Department overall advisories. [CDC's April 13, 2022 announcement](https://archive.cdc.gov/www_cdc_gov/media/releases/2022/s0413-mask-order.html) documents a subsequent change to its Level 4 notice criteria, effective April 18. These establish changing policy context. They do **not** establish that this regime change caused our model's errors, which regime applies to each undated CSV row, or that deleting COVID text will improve transfer.

Current status: verified historical-to-feed performance decline; plausible policy, formatting, template, and source-composition shifts; unresolved causal attribution. No new model should be considered for production until evaluated on a new independent set with verified provenance and a selection protocol fixed beforehand.

## Reproduce and inspect

```sh
uv run --frozen python -m scripts.audit_label_transfer
uv run --frozen python -m scripts.audit_source_provenance
```

Both refuse an existing report to preserve evidence. Generated reports are ignored under `.local/research/bert/investigation-v3c/`; the original prediction files and dataset manifests are unchanged. The numeric-normalization lineage method matches the legacy exporter but deliberately does not infer source dates.

Validation: 67 unit tests pass. The previous 30 Postgres integration tests remain applicable; no database logic changed in this audit.

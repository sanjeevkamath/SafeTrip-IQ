# BERT retraining v2

Historical experiment record. The current follow-up is documented in [bert-investigation-v3.md](bert-investigation-v3.md). Commands below require the original v2 cleaner; they intentionally fail version checks with later preprocessing.

This experiment removes direct country/advisory-label cues and keeps similar text out of different dataset splits. Baseline datasets, the old checkpoint, and production scores remain unchanged. Generated datasets, reports, and candidate weights stay in ignored `.local/research/bert/`.

## Data audit

The frozen sources contain 1,107 training and 502 test rows, with only `label,text` columns. Country and date provenance is unavailable. Direct level/recommendation cues appear in 1,097 training and 498 test rows. The old split shares 136 groups of identical normalized advisories. After v2 cleaning, 1,609 source rows reduce to 998 unique nonempty texts, with no conflicting exact-text labels.

Preprocessing is shared with production inference: `advisory-no-country-labels-v2`. Deduplication uses cleaned text; closely similar texts are grouped with 3-word-shingle Jaccard similarity at 0.85 and transitive connected components. The result has 795 similarity groups, the largest containing 59 unique texts. Deterministic approximate class stratification allocates whole groups into 698 training, 150 validation, and 150 test rows. All four classes occur in each split. This heuristic does not establish a country/time holdout or rule out every form of leakage. The manifest pins source hashes, preprocessing code hashes, generated file hashes, label mapping, split counts, and seed.

## Evaluation and selection

The old checkpoint achieved 67.33% accuracy and 0.6987 macro-F1 on the newly cleaned validation set, with high-risk underestimation on 11 of 61 Level 3/4 examples. This is diagnostic: that checkpoint may have seen these rows during training. Its saved 0.9457 F1 came from different inputs/splits and a different averaging scheme; those numbers cannot be directly compared.

Candidate training starts from cached pretrained `bert-base-uncased`, revision `86b5e0934494bd15c9632b12f734a8a67f723594`, with a new four-class head. Class IDs 0–3 mean advisory Levels 1–4. Default training uses three epochs, learning rate 2e-5, AdamW, 10% warmup, weight decay 0.01, gradient clipping at 1.0, seed 42, max length 256, batches of 4 with accumulation of 4 (effective batch 16). Precision is float32. Validation macro-F1 selects the saved candidate epoch. Accelerator results may not be bit-for-bit deterministic despite pinned inputs/seeds.

The validation report includes per-class precision/recall/F1, a confusion matrix, and high-risk underestimation. The reserved test split is used only after model selection. Repeatedly tuning against final test results would invalidate it as a holdout. Longer advisories are truncated at 256 tokens, matching runtime inference; risk evidence beyond that cutoff remains a limitation.

## Commands

From the repository using the existing uv environment:

```sh
uv run --frozen python -m scripts.audit_bert_data
uv run --frozen python -m scripts.prepare_bert_dataset
uv run --frozen python -m scripts.evaluate_bert_validation
uv run --frozen python -m research.bert.train --device mps --output .local/research/bert/candidate-v2-01
```

Dataset, evaluation, and candidate paths refuse overwrites; use new versioned paths for new experiments. The trainer reads only training and validation files. It requires the pinned pretrained safetensors cache and never silently downloads weights. The Mac GPU requires an execution context with MPS access; `--device cpu` is supported but slower. Nothing in these commands writes to the hosted database or starts an AWS task.

After the chosen candidate finishes, explicitly evaluate its test split:

```sh
uv run --frozen python -m scripts.evaluate_bert_validation \
  --model .local/research/bert/candidate-v2-01/model \
  --split test --final-test \
  --output .local/research/bert/candidate-v2-01/final-test.json
```

Review the results before promotion. Candidate packaging needs its own file hashes and model manifest, then CPU inference verification against the AWS worker format. Do not replace the frozen baseline manifest/checkpoint simply because training finished. Model promotion, S3 upload, and production refresh validation are separate deployment steps.

## First candidate results — October 13, 2026

`candidate-v2-01` trained locally on the Mac MPS GPU in 265 seconds, using cached pretrained weights and the defaults above. Epoch 2 was selected by validation macro-F1; epoch 3 had higher accuracy but lower macro-F1. The selected safetensors model and tokenizer were then loaded on CPU for the reserved final test.

| Metric | Selected validation epoch | Final test |
| --- | ---: | ---: |
| Rows | 150 | 150 |
| Accuracy | 69.33% | 63.33% |
| Macro-F1 | 0.6738 | 0.5871 |
| Level 3 recall | 37.50% | 28.13% |
| Level 4 recall | 51.72% | 37.93% |
| Level 3/4 underestimation rate | 52.46% | 59.02% |

**Decision: do not promote this candidate.** It loads and runs correctly, but it frequently predicts lower levels for high-risk examples. The integrity manifest at `.local/research/bert/candidate-v2-01/model-manifest.json` records its evaluated model fingerprint, file hashes, provenance, and test metrics. It remains a separate local research artifact; no AWS upload or production database update was performed.

Next experiments should address the weak high-risk validation recall, review retained training text and class imbalance, and consider class-weighted loss or an ordinal objective. Use validation data for these decisions. The test report is now consumed evidence for this first candidate: do not repeatedly optimize against its results or present later tuning on this test as independent evaluation. Recovering dated/country-tagged raw advisories would enable a stronger prospective holdout and help distinguish model weakness from dataset limitations.

To generate the manifest for a separately evaluated candidate:

```sh
uv run --frozen python -m scripts.manifest_bert_candidate \
  --candidate .local/research/bert/candidate-v2-01
```

This command refuses an existing manifest and checks that the weights match the final evaluation. It does not approve or deploy the model.

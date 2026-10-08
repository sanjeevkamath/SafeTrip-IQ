# Research and experiments

This directory contains model development and historical data preparation. The website, database writers, and baseline verifier do not import it. Running a deployed worker should require a versioned fitted model, not these training scripts.

## Model experiments

| Entry point | Input | Output |
| --- | --- | --- |
| `bert/train.py` (formerly `pipeline/BERT/sentiment.py`) | Frozen `data/baseline/bert/train.csv` and `test.csv` | New timestamped directory under `.local/research/bert/` |
| `clustering/fit.py` (formerly `pipeline/clustering/clustering.py`) | Frozen `data/baseline/clustering/features.csv` | New timestamped directory under `.local/research/clustering/` |

Both entry points resolve paths relative to the repository, run only when explicitly invoked, and expose `--help` without loading ML dependencies. Importing them does not download models, train, or create output directories. Their outputs cannot replace the retained `results/checkpoint-189` or the frozen cluster output through the default workflow.

To inspect the commands without running training:

```sh
uv run --frozen --extra research python research/bert/train.py --help
uv run --frozen --extra research python research/clustering/fit.py --help
```

Omitting `--help` executes the experiment. BERT training can download `bert-base-uncased` and consume substantial compute. Its training/test overlap and split methodology are still unresolved; this move is not a new accuracy evaluation or a reproduction of the original training run. No BERT retraining was performed as part of the reorganization.

Use `uv run --frozen python -m scripts.verify_baseline --with-clustering` to reproduce the verified historical cluster assignments without generating research charts.

## Historical material

`bert/json_to_csv.py`, `bert/wayback/`, the remaining clustering scripts/data/charts, and `legacy_data_preparation/` preserve the original exploration. Some retain working-directory assumptions, missing external inputs, import-time execution, or in-place data transformations. They are archival source material, not supported worker commands. Keep them until the input provenance and replacement pipeline are established; do not chain them together to refresh production data.

Historical charts in `clustering/output/` remain as evidence. Newly generated charts go to `.local/research/`. Multiple similarly named datasets are preserved deliberately; see the repository guide for their status.

## Existing advisory cleaning: provenance to recover

The project author recalls removing identifying information and explicit advisory-level sentences before training. Preserve that intent when extracting the shared preprocessing module. The repository contains several partial cleaning implementations:

- `bert/wayback/wayback_to_csv.py`: `clean_text_for_bert` removes selected boilerplate and normalizes whitespace. Its caller extracts the label from the title and passes only the body as input. `should_skip_short_advisory` filters short texts and Level 1 texts beginning with “Exercise normal precautions.” It does not generally remove severity phrases from retained bodies.
- `bert/json_to_csv.py`: `clean_text` lowercases, removes URLs/digits and some characters, and normalizes whitespace.
- `../pipeline/src/safetrip/ingestion/advisories.py` (extracted from `db/scripts/populate_travel_advisories.py`): `clean_html_to_text` removes HTML and selected boilerplate before storing descriptions used by inference. Its rules differ from the archived training preparation.

A case-insensitive phrase scan of the preserved CSVs on 2026-10-08 found explicit `level [1-4]` in 352/1107 training rows and 98/502 test rows; “do not travel” occurs in 445 training rows and 164 test rows. Counts overlap and include possible regional advice or quoted update notices. They flag data to inspect, not a measurement of model reliance on labels. The current training entry point tokenizes these CSV texts without an additional sentence-removal step.

The exact comprehensive cleaner described by the author, and whether it produced the deployed checkpoint's inputs, have not yet been identified. Investigate before replacing preprocessing or retraining. Keep the captured baseline unchanged until the intended cleaning rules, input provenance, and evaluation split are agreed.

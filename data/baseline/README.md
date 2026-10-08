# Frozen baseline inputs and outputs

These files are the reference data for refactoring. They are not destinations for new training or ingestion outputs.

| File | Previous location | Purpose |
| --- | --- | --- |
| `bert/train.csv` | `pipeline/BERT/train.csv` | Preserved training input |
| `bert/test.csv` | `pipeline/BERT/test.csv` | Preserved test input, with known overlap with training data |
| `clustering/features.csv` | `pipeline/clustering/data/clustering_ready.csv` | 169-row frozen feature population |
| `clustering/clusters.csv` | `pipeline/clustering/output/clustering_output.csv` | 168-country expected raw cluster assignments |

All four files retain their pre-move SHA-256 hashes in `docs/baseline/artifacts.json`. The clustering fit includes one feature row without an ISO3 code; comparison with expected output excludes that unidentified row, preserving the historical behavior.

After `uv sync --frozen`, run `uv run --frozen python -m scripts.verify_baseline` from the repository root to verify hashes and the 212 score fixtures. Add `--with-clustering` using the uv environment to reproduce cluster assignments.

`clustering/clusters.csv` contains raw cluster IDs, not ranked risk tiers. The legacy database population script now reads this file by default, but remains a writer requiring a deliberate invocation and appropriate credentials. This reorganization does not make the historical remapping script safe to rerun.

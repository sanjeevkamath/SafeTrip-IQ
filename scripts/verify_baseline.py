"""Offline regression verification; no credentials, downloads, or DB writes.

python -m scripts.verify_baseline            # 212 score fixtures
python -m scripts.verify_baseline --with-model  # also check artifact hashes/inference
python -m scripts.verify_baseline --with-clustering  # reproduce saved cluster IDs
"""

import argparse
import hashlib
import json
from pathlib import Path

from safetrip.scoring.legacy import legacy_safety_score

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-model", action="store_true")
    parser.add_argument("--with-clustering", action="store_true")
    parser.add_argument("--model-path", type=Path, default=ROOT / "results/checkpoint-189")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "docs/baseline/artifacts.json").read_text())
    for name, expected in manifest["data_files"].items():
        if sha256(ROOT / name) != expected["sha256"]:
            raise AssertionError(f"Baseline dataset differs: {name}")
    fixture = json.loads((ROOT / "tests/fixtures/legacy_scores.json").read_text())
    for row in fixture["rows"]:
        observed = legacy_safety_score(row["bert_score"], row["clustering_score"])
        if observed != row["safe_trip_score"]:
            raise AssertionError(f"Score mismatch for {row['iso3']}")
    print(f"PASS: {len(fixture['rows'])} captured scores reproduced exactly, offline.")
    if args.with_model:
        import torch
        from safetrip.inference.bert import load_model, score_texts

        model_path = args.model_path if args.model_path.is_absolute() else ROOT / args.model_path
        for name, expected in manifest["model_files"].items():
            if sha256(model_path / name) != expected["sha256"]:
                raise AssertionError(f"Model artifact differs: {name}")
        examples = json.loads((ROOT / "tests/fixtures/bert_predictions.json").read_text())
        torch.set_num_threads(1)
        tokenizer, model = load_model(model_path)
        model.to("cpu").eval()
        actual = score_texts([row["text"] for row in examples["rows"]], tokenizer, model, "cpu").tolist()
        expected = [row["expected_class_id"] for row in examples["rows"]]
        if actual != expected:
            raise AssertionError(f"BERT regression mismatch: expected {expected}, got {actual}")
        print(f"PASS: artifact hashes and {len(actual)} captured CPU predictions match.")
        print("These are behavioral regression checks, not evidence of model accuracy.")
    if args.with_clustering:
        import pandas as pd
        from sklearn.cluster import KMeans

        inputs = pd.read_csv(ROOT / "data/baseline/clustering/features.csv")
        saved = pd.read_csv(ROOT / "data/baseline/clustering/clusters.csv")
        features = ["gpi_score", "ppi_score", "gti_score", "pvi_score"]
        # Preserve the legacy fit population, including its one row without ISO3.
        predicted = KMeans(n_clusters=5, random_state=42, n_init="auto").fit_predict(inputs[features])
        actual = inputs[["iso3"]].assign(predicted=predicted).dropna(subset=["iso3"])
        joined = saved.merge(actual, on="iso3", how="outer", validate="one_to_one", indicator=True)
        if not (joined["_merge"] == "both").all() or not (joined["cluster"] == joined["predicted"]).all():
            raise AssertionError("Clustering output differs from the captured baseline")
        print(f"PASS: {len(joined)} saved cluster IDs reproduced from frozen features.")


if __name__ == "__main__":
    main()

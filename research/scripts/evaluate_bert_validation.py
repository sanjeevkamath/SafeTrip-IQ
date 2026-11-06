"""Evaluate validation data, or explicitly evaluate a completed candidate's final test."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from safetrip.ingestion.advisories import CLEANING_VERSION

ROOT = Path(__file__).resolve().parents[2]


def metrics(labels, predictions):
    if not labels or len(labels) != len(predictions):
        raise ValueError("Expected equally sized nonempty labels and predictions.")
    matrix = [[0] * 4 for _ in range(4)]
    for actual, predicted in zip(labels, predictions):
        if actual not in range(4) or predicted not in range(4):
            raise ValueError("Class ID outside 0..3.")
        matrix[actual][predicted] += 1
    per_class = {}
    for label in range(4):
        tp = matrix[label][label]
        support = sum(matrix[label])
        predicted_count = sum(row[label] for row in matrix)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        per_class[str(label + 1)] = {"support": support, "precision": precision, "recall": recall,
                                   "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    high_risk = [(a, p) for a, p in zip(labels, predictions) if a >= 2]
    return {"accuracy": sum(a == p for a, p in zip(labels, predictions)) / len(labels),
            "macro_f1": sum(row["f1"] for row in per_class.values()) / 4,
            "per_advisory_level": per_class,
            "confusion_matrix_actual_rows_predicted_columns": matrix,
            "high_risk_predicted_low_risk_rate": sum(p < 2 for a, p in high_risk) / len(high_risk) if high_risk else None,
            "high_risk_underestimation_rate": sum(p < a for a, p in high_risk) / len(high_risk) if high_risk else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / ".local/research/bert/dataset-v2")
    parser.add_argument("--model", type=Path, default=ROOT / "results/checkpoint-189")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/research/bert/baseline-validation-v2.json")
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--final-test", action="store_true", help="Explicitly consume the reserved test split for a completed candidate.")
    args = parser.parse_args()
    training = None
    if args.split == "test":
        if not args.final_test:
            parser.error("Reserved test evaluation requires --final-test.")
        training = json.loads((args.model.parent / "training-report.json").read_text())
        if training.get("status") != "succeeded" or training.get("test_set_used"):
            raise ValueError("Final test requires a completed candidate selected without test data.")
    if args.output.exists():
        raise FileExistsError("Evaluation output exists; choose a new report path.")
    manifest = json.loads((args.dataset / "manifest.json").read_text())
    if manifest["cleaning_version"] != CLEANING_VERSION:
        raise ValueError("Dataset cleaner differs from runtime preprocessing.")
    if training and training["dataset_manifest_sha256"] != hashlib.sha256((args.dataset / "manifest.json").read_bytes()).hexdigest():
        raise ValueError("Candidate was trained against a different dataset manifest.")
    source = args.dataset / (args.split + ".jsonl")
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["artifacts"][source.name]:
        raise ValueError("Validation data differs from its manifest.")
    for name, expected in manifest["cleaner_source_hashes"].items():
        if hashlib.sha256((ROOT / "pipeline/src/safetrip/ingestion" / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Cleaner code changed since dataset preparation.")
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    from safetrip.inference.bert import load_model, score_texts
    from safetrip.inference.integrity import model_fingerprint
    import torch
    torch.set_num_threads(2)
    torch.manual_seed(42)
    started = time.monotonic()
    version = model_fingerprint(args.model)
    tokenizer, model = load_model(args.model)
    model.to("cpu").eval()
    predictions = []
    for start in range(0, len(rows), 8):
        batch = rows[start:start + 8]
        predictions.extend(int(value) for value in score_texts([row["text"] for row in batch], tokenizer, model, "cpu"))
        print(f"{args.split.title()} inference: {len(predictions)}/{len(rows)}", flush=True)
    report = {"model_version": version, "cleaning_version": CLEANING_VERSION,
              "dataset_manifest_sha256": hashlib.sha256((args.dataset / "manifest.json").read_bytes()).hexdigest(),
              "split": args.split, "rows": len(rows), "device": "cpu",
              "seconds": round(time.monotonic() - started, 3),
              "metrics": metrics([row["label"] for row in rows], predictions),
              "predictions": [{"text_sha256": row["text_sha256"], "label": row["label"], "prediction": prediction}
                              for row, prediction in zip(rows, predictions)],
              "limitations": ("Similarity-grouped evaluation; no country/time holdout and unknown semantic overlap."
                              if training else "Existing checkpoint exposure to these rows is unknown; diagnostic comparison only.")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report["metrics"], indent=2))
    print(f"{args.split.title()} report saved to {args.output}.")


if __name__ == "__main__":
    main()

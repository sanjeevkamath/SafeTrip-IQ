"""Score a locked validation-selected model on an overlap-filtered official feed."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from safetrip.inference.integrity import model_fingerprint
from scripts.evaluate_bert_validation import metrics

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--investigation", type=Path, default=ROOT / ".local/research/bert/investigation-v3c")
    parser.add_argument("--holdout", type=Path, default=ROOT / ".local/research/bert/fresh-holdout-v3")
    args = parser.parse_args()
    comparison = json.loads((args.investigation / "comparison.json").read_text())
    selected = max(comparison, key=lambda row: row["macro_f1"])["experiment"]
    lock = args.investigation / "selection-lock.json"
    choice = {"experiment": selected, "criterion": "highest validation macro-F1", "holdout_used_for_selection": False,
              "model_version": model_fingerprint(args.investigation / selected / "model"),
              "comparison_sha256": hashlib.sha256((args.investigation / "comparison.json").read_bytes()).hexdigest()}
    if lock.exists():
        if json.loads(lock.read_text()) != choice:
            raise ValueError("Selection already locked to different weights or results.")
    else:
        with lock.open("x") as stream:
            json.dump(choice, stream, indent=2)
    source = args.holdout / "holdout.jsonl"
    manifest = json.loads((args.holdout / "manifest.json").read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["holdout_sha256"]:
        raise ValueError("Holdout file changed since preparation.")
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    from safetrip.inference.bert import load_model, score_texts
    import torch
    torch.set_num_threads(2)
    for name in dict.fromkeys(("control256", selected)):
        output = args.investigation / (name + "-fresh-evaluation.json")
        if output.exists():
            raise FileExistsError("Fresh evaluation already exists; do not repeatedly tune against its results.")
        training = json.loads((args.investigation / name / "training-report.json").read_text())
        if training["dataset_manifest_sha256"] != manifest["historical_manifest_sha256"]:
            raise ValueError("Holdout filtering used another historical dataset.")
        started = time.monotonic()
        model_path = args.investigation / name / "model"
        tokenizer, model = load_model(model_path)
        model.to("cpu").eval()
        predictions = []
        for start in range(0, len(rows), 8):
            batch = rows[start:start + 8]
            predictions.extend(int(value) for value in score_texts([r["text"] for r in batch], tokenizer, model, "cpu"))
            print(f"Fresh evaluation {name}: {len(predictions)}/{len(rows)}", flush=True)
        report = {"experiment": name, "selection": choice, "split": "fresh_official_feed_filtered",
                  "model_version": model_fingerprint(model_path), "cleaning_version": manifest["cleaning_version"],
                  "dataset_manifest_sha256": training["dataset_manifest_sha256"],
                  "holdout_manifest_sha256": hashlib.sha256((args.holdout / "manifest.json").read_bytes()).hexdigest(),
                  "rows": len(rows), "seconds": round(time.monotonic() - started, 3),
                  "metrics": metrics([r["label"] for r in rows], predictions),
                  "predictions": [{"text_sha256": r["text_sha256"], "group_id": r["group_id"],
                                   "label": r["label"], "prediction": prediction}
                                  for r, prediction in zip(rows, predictions)],
                  "limitations": manifest["limitations"]}
        with output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(name + " fresh metrics: " + json.dumps(report["metrics"]), flush=True)
        del model, tokenizer


if __name__ == "__main__":
    main()

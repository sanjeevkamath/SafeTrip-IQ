"""Create an integrity manifest for an evaluated candidate; no production promotion."""
import argparse
import hashlib
import json
from pathlib import Path

from safetrip.inference.integrity import MODEL_FILES, model_fingerprint, verify_model


def candidate_manifest(candidate):
    candidate = Path(candidate)
    training = json.loads((candidate / "training-report.json").read_text())
    evaluation = json.loads((candidate / "final-test.json").read_text())
    if training.get("status") != "succeeded" or training.get("test_set_used"):
        raise ValueError("Candidate must be selected using validation data only.")
    if evaluation.get("split") != "test" or evaluation.get("dataset_manifest_sha256") != training["dataset_manifest_sha256"]:
        raise ValueError("Final test does not match the candidate training dataset.")
    model = candidate / "model"
    fingerprint = model_fingerprint(model)
    if evaluation.get("model_version") != fingerprint:
        raise ValueError("Model changed since final evaluation.")
    files = {name: {"bytes": (model / name).stat().st_size,
                    "sha256": hashlib.sha256((model / name).read_bytes()).hexdigest()} for name in MODEL_FILES}
    return {"model_files": files, "model_version": fingerprint,
            "cleaning_version": training["cleaning_version"], "label_mapping": training["label_mapping"],
            "base_revision": training["base_revision"],
            "dataset_manifest_sha256": training["dataset_manifest_sha256"],
            "best_epoch": training["best_epoch"], "test_metrics": evaluation["metrics"],
            "deployment_status": "candidate_only_not_promoted"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    manifest = candidate_manifest(args.candidate)
    output = args.candidate / "model-manifest.json"
    with output.open("x") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    verify_model(args.candidate / "model", output)
    print(f"Verified candidate manifest saved to {output}. Production artifacts remain unchanged.")


if __name__ == "__main__":
    main()

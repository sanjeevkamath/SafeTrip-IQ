"""Run fixed local validation-only experiments sequentially; no cloud or test selection."""
import json
import argparse
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = (
    ("control256", "head", 256, "none", 2, 8),
    ("long512", "head", 512, "none", 2, 8),
    ("balanced512", "head", 512, "balanced", 2, 8),
    ("balanced-tail512", "head_tail", 512, "balanced", 2, 8),
    ("balanced-chunks256", "chunks", 256, "balanced", 1, 16),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/research/bert/investigation-v3")
    parser.add_argument("--dataset", type=Path, default=ROOT / ".local/research/bert/dataset-v3")
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan = {"experiments": EXPERIMENTS, "epochs": 3, "seed": 42, "learning_rate": 2e-5,
            "selection": "validation macro-F1; report high-risk recall/underestimation separately",
            "test_used_for_selection": False}
    plan_path = root / "plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text()) != json.loads(json.dumps(plan)):
        raise ValueError("Existing investigation uses another plan.")
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    for name, policy, length, weighting, batch, accumulation in EXPERIMENTS:
        output = root / name
        report_path = output / "training-report.json"
        if report_path.exists():
            previous = json.loads(report_path.read_text())
            if previous.get("status") == "succeeded":
                print(f"Already complete: {name}", flush=True)
                continue
            raise ValueError(f"Incomplete experiment {name}; inspect rather than overwrite it.")
        command = [sys.executable, "-m", "research.bert.train", "--device", "mps", "--dataset",
                   str(args.dataset), "--output", str(output), "--epochs", "3",
                   "--max-length", str(length), "--input-policy", policy, "--class-weighting", weighting,
                   "--batch-size", str(batch), "--accumulation", str(accumulation)]
        print(f"Starting experiment: {name}", flush=True)
        with (root / (name + ".log")).open("x") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            started = time.monotonic()
            try:
                while process.poll() is None:
                    time.sleep(20)
                    lines = (root / (name + ".log")).read_text().splitlines()
                    progress = next((line for line in reversed(lines) if line.startswith("Epoch ")), "initializing")
                    print(f"{name}: {progress}; elapsed {int(time.monotonic() - started)}s", flush=True)
                if process.returncode:
                    raise RuntimeError(f"Experiment {name} failed; inspect its local log.")
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
        report = json.loads(report_path.read_text())
        chosen = report["history"][report["best_epoch"] - 1]["validation"]
        print(f"Completed {name}: " + json.dumps(chosen), flush=True)
    comparison = []
    for name, *_ in EXPERIMENTS:
        report = json.loads((root / name / "training-report.json").read_text())
        metrics = report["history"][report["best_epoch"] - 1]["validation"]
        comparison.append({"experiment": name, "best_epoch": report["best_epoch"], "seconds": report["seconds"],
                           "accuracy": metrics["accuracy"], "macro_f1": metrics["macro_f1"],
                           "level3_recall": metrics["per_advisory_level"]["3"]["recall"],
                           "level4_recall": metrics["per_advisory_level"]["4"]["recall"],
                           "high_risk_underestimation": metrics["high_risk_underestimation_rate"]})
    comparison.sort(key=lambda row: row["macro_f1"], reverse=True)
    (root / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print("Investigation complete; no test evaluation or production promotion.", flush=True)


if __name__ == "__main__":
    main()

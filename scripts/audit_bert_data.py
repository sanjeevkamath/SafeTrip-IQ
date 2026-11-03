"""Offline dataset audit before retraining; frozen source files remain unchanged."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from safetrip.ingestion.advisories import (
    CLEANING_VERSION, COUNTRY_NAME_PATTERN, LEVEL_PATTERN,
    RECOMMENDATION_PATTERN, clean_html_to_text,
)

ROOT = Path(__file__).resolve().parents[1]


def audit(sources):
    records = []
    summaries = {}
    for split, path in sources.items():
        path = Path(path)
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["label", "text"]:
                raise ValueError("Expected label,text columns; provenance metadata is unavailable in these inputs.")
            rows = list(reader)
        counts = Counter()
        cues = countries = empty = changed = 0
        for number, row in enumerate(rows, start=2):
            if row["label"] not in {"1", "2", "3", "4"}:
                raise ValueError(f"Invalid advisory label at {split} row {number}.")
            text = row["text"]
            if not text.strip():
                raise ValueError(f"Missing source text at {split} row {number}.")
            cleaned = clean_html_to_text(text)
            counts[row["label"]] += 1
            cues += bool(LEVEL_PATTERN.search(text) or RECOMMENDATION_PATTERN.search(text))
            countries += bool(COUNTRY_NAME_PATTERN.search(text.replace("’", "'")))
            empty += not cleaned
            changed += cleaned != text
            records.append({"source_split": split, "source_row": number,
                            "label": int(row["label"]), "raw": text, "cleaned": cleaned})
        summaries[split] = {"rows": len(rows), "labels": dict(sorted(counts.items())),
                            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "rows_with_direct_label_cues": cues,
                            "rows_with_country_names": countries,
                            "rows_changed_by_cleaning": changed,
                            "empty_after_cleaning": empty,
                            "available_columns": ["label", "text"]}

    duplicates = {}
    for representation in ("raw", "cleaned"):
        groups = defaultdict(list)
        for row in records:
            text = " ".join(row[representation].lower().split())
            if text:
                groups[text].append(row)
        repeated = [rows for rows in groups.values() if len(rows) > 1]
        crossed = [rows for rows in repeated if len({r["source_split"] for r in rows}) > 1]
        conflicts = [rows for rows in repeated if len({r["label"] for r in rows}) > 1]
        duplicates[representation] = {
            "unique_nonempty_texts": len(groups),
            "duplicate_groups": len(repeated),
            "redundant_rows": sum(len(rows) - 1 for rows in repeated),
            "cross_split_groups": len(crossed),
            "cross_split_rows": sum(len(rows) for rows in crossed),
            "conflicting_label_groups": len(conflicts),
            "conflicting_label_rows": sum(len(rows) for rows in conflicts),
            "conflicts": [{"text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                           "rows": [{k: row[k] for k in ("source_split", "source_row", "label")} for row in rows]}
                          for text, rows in groups.items() if len({r["label"] for r in rows}) > 1],
        }
    return {"cleaning_version": CLEANING_VERSION, "sources": summaries,
            "duplicate_analysis": duplicates,
            "country_time_provenance_available": False,
            "limitations": ["Country and date cannot be reliably reconstructed from label,text alone.",
                            "Exact normalized duplicates only; near-duplicate leakage still needs analysis.",
                            "Existing checkpoint training input identity is not established.",
                            "Its evaluation on newly derived splits is diagnostic, not an independent holdout."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/research/bert/data-audit.json")
    args = parser.parse_args()
    report = audit({split: ROOT / f"data/baseline/bert/{split}.csv" for split in ("train", "test")})
    state_path = ROOT / "results/checkpoint-189/trainer_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        report["checkpoint_training_state"] = {key: state.get(key) for key in
                                               ("epoch", "global_step", "best_metric", "train_batch_size")}
        report["checkpoint_training_state"]["provenance_note"] = (
            "Saved metrics reflect old inputs/splits; they do not validate the new preprocessing. "
            "Pickle training_args/optimizer files were not loaded.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "duplicate_analysis"}, indent=2))
    print("Duplicate summary: " + json.dumps({key: {k: v for k, v in value.items() if k != "conflicts"}
                                               for key, value in report["duplicate_analysis"].items()}))
    print(f"Audit saved to {args.output}; no training or database writes performed.")


if __name__ == "__main__":
    main()

"""Reclean original rows while preserving v2 group/split assignments for experiments."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from safetrip.ingestion.advisories import CLEANING_VERSION, clean_html_to_text

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=ROOT / ".local/research/bert/dataset-v2")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/research/bert/dataset-v3")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Experiment dataset already exists.")
    old = json.loads((args.original / "manifest.json").read_text())
    sources = {}
    for split in ("train", "test"):
        path = ROOT / f"data/baseline/bert/{split}.csv"
        if hashlib.sha256(path.read_bytes()).hexdigest() != old["source_hashes"][split]:
            raise ValueError("Original source hash changed.")
        sources[split] = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    report = {**old, "cleaning_version": CLEANING_VERSION, "artifacts": {}, "splits": {},
              "split_policy": "inherit v2 group membership; expand text variants changed by cleaning within the same group",
              "parent_manifest_sha256": hashlib.sha256((args.original / "manifest.json").read_bytes()).hexdigest()}
    outputs = {}
    all_hashes = set()
    changed = 0
    for split in ("train", "validation", "test"):
        path = args.original / (split + ".jsonl")
        if hashlib.sha256(path.read_bytes()).hexdigest() != old["artifacts"][path.name]:
            raise ValueError("Parent split hash changed.")
        by_hash = {}
        for line in path.read_text().splitlines():
            previous = json.loads(line)
            for reference in previous["source_rows"]:
                raw = sources[reference["source_split"]][reference["source_row"] - 2]
                text = clean_html_to_text(raw["text"])
                if not text:
                    raise ValueError("Recleaning produced empty text; review before continuing.")
                key = hashlib.sha256(text.encode()).hexdigest()
                row = by_hash.setdefault(key, {"text": text, "text_sha256": key,
                                             "label": previous["label"], "group_id": previous["group_id"], "source_rows": []})
                if row["label"] != previous["label"] or row["group_id"] != previous["group_id"]:
                    raise ValueError("New identical text crosses original groups or labels; split review required.")
                row["source_rows"].append(reference)
                changed += text != previous["text"]
        if all_hashes & by_hash.keys():
            raise ValueError("New cleaner created cross-split duplicates.")
        all_hashes.update(by_hash)
        outputs[split] = [by_hash[key] for key in sorted(by_hash)]
        report["splits"][split] = {"rows": len(by_hash),
                                   "groups": len({row["group_id"] for row in by_hash.values()}),
                                   "class_counts": {str(label): sum(row["label"] == label for row in by_hash.values()) for label in range(4)}}
    report["unique_cleaned_rows"] = len(all_hashes)
    report["source_rows_changed_by_v3"] = changed
    report["cleaner_source_hashes"] = {name: hashlib.sha256((ROOT / "pipeline/src/safetrip/ingestion" / name).read_bytes()).hexdigest()
                                      for name in ("advisories.py", "country_names.py")}
    args.output.mkdir(parents=True)
    for split, rows in outputs.items():
        path = args.output / (split + ".jsonl")
        path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows))
        report["artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("cleaning_version", "source_rows_changed_by_v3", "splits")}, indent=2))


if __name__ == "__main__":
    main()

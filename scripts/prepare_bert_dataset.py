"""Create immutable cleaned/grouped experiment inputs without changing baseline data."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

from safetrip.ingestion.advisories import CLEANING_VERSION, clean_html_to_text

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(sources, *, seed=42, similarity=0.85):
    unique = {}
    rejected = []
    for split, path in sources.items():
        with Path(path).open(newline="", encoding="utf-8") as stream:
            for number, row in enumerate(csv.DictReader(stream), start=2):
                if row.get("label") not in {"1", "2", "3", "4"} or not row.get("text", "").strip():
                    raise ValueError("Invalid training source row.")
                text = clean_html_to_text(row["text"])
                reference = {"source_split": split, "source_row": number}
                if not text:
                    rejected.append({**reference, "reason": "empty_after_cleaning"})
                    continue
                key = digest(text)
                entry = unique.setdefault(key, {"text": text, "labels": set(), "source_rows": []})
                entry["labels"].add(int(row["label"]) - 1)
                entry["source_rows"].append(reference)
    records = []
    for key, entry in sorted(unique.items()):
        if len(entry["labels"]) != 1:
            rejected.append({"text_sha256": key, "reason": "conflicting_labels", "source_rows": entry["source_rows"]})
        else:
            records.append({"text_sha256": key, "text": entry["text"],
                            "label": next(iter(entry["labels"])), "source_rows": entry["source_rows"]})

    # Exact 3-word shingle Jaccard, followed by connected components. The threshold
    # is a documented heuristic, not proof that all semantic duplicates are grouped.
    def shingles(text):
        words = re.findall(r"\w+", text)
        return set(zip(words, words[1:], words[2:])) if len(words) >= 3 else {tuple(words)}
    sets = [shingles(row["text"]) for row in records]
    parents = list(range(len(records)))
    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    edges = 0
    for i, left in enumerate(sets):
        for j in range(i):
            right = sets[j]
            if min(len(left), len(right)) / max(len(left), len(right)) < similarity:
                continue
            overlap = len(left & right)
            if overlap / (len(left) + len(right) - overlap) >= similarity:
                parents[root(i)] = root(j)
                edges += 1
    grouped = defaultdict(list)
    for i, row in enumerate(records):
        grouped[root(i)].append(row)
    groups = list(grouped.values())
    for group in groups:
        group_id = digest("\n".join(sorted(row["text_sha256"] for row in group)))
        for row in group:
            row["group_id"] = group_id
    # Allocate whole groups while minimizing incremental class-count deviation.
    # This is deterministic approximate stratification, not a random row split.
    groups.sort(key=lambda group: (-len(group), digest(str(seed) + group[0]["group_id"])))
    totals = Counter(row["label"] for row in records)
    proportions = {"train": 0.70, "validation": 0.15, "test": 0.15}
    counts = {split: Counter() for split in proportions}
    splits = {split: [] for split in proportions}
    for group in groups:
        labels = Counter(row["label"] for row in group)
        def penalty(split):
            result = 0.0
            for label, added in labels.items():
                target = totals[label] * proportions[split]
                current = counts[split][label]
                result += ((current + added - target) ** 2 - (current - target) ** 2) / max(target, 1)
            return result
        chosen = min(proportions, key=penalty)
        splits[chosen].extend(group)
        counts[chosen].update(labels)
    if any(set(counts[split]) != {0, 1, 2, 3} for split in splits):
        raise ValueError("Grouped splits cannot represent all four classes; review grouping/data before training.")
    report = {"cleaning_version": CLEANING_VERSION, "seed": seed,
              "label_mapping": {str(i): i - 1 for i in range(1, 5)},
              "grouping": {"method": "normalized exact text plus 3-word-shingle Jaccard connected components",
                           "threshold": similarity, "near_duplicate_edges": edges,
                           "groups": len(groups), "largest_group_rows": max(map(len, groups))},
              "unique_cleaned_rows": len(records), "rejected": rejected,
              "splits": {split: {"rows": len(rows), "class_counts": dict(sorted(counts[split].items())),
                                 "groups": len({row["group_id"] for row in rows})}
                         for split, rows in splits.items()},
              "limitations": ["No country/time provenance; these are similarity-grouped splits.",
                               "Near-duplicate threshold is heuristic; manual review remains necessary.",
                               "Existing checkpoint may have trained on these rows; its metrics are diagnostic.",
                               "Test data is reserved for final candidate evaluation, not model selection."]}
    return splits, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/research/bert/dataset-v2")
    args = parser.parse_args()
    sources = {split: ROOT / f"data/baseline/bert/{split}.csv" for split in ("train", "test")}
    if args.output.exists():
        raise FileExistsError("Dataset output already exists; choose a new version directory.")
    splits, report = prepare(sources)
    args.output.mkdir(parents=True, exist_ok=False)
    report["source_hashes"] = {split: hashlib.sha256(path.read_bytes()).hexdigest() for split, path in sources.items()}
    report["artifacts"] = {}
    for split, rows in splits.items():
        path = args.output / (split + ".jsonl")
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                                for row in sorted(rows, key=lambda row: row["text_sha256"])))
        report["artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["cleaner_source_hashes"] = {name: hashlib.sha256((ROOT / "pipeline/src/safetrip/ingestion" / name).read_bytes()).hexdigest()
                                      for name in ("advisories.py", "country_names.py")}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in {"artifacts", "cleaner_source_hashes", "source_hashes", "limitations"}}, indent=2))
    print(f"Frozen experiment inputs saved to {args.output}. Test split is reserved; no model training performed.")


if __name__ == "__main__":
    main()

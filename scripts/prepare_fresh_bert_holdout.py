"""Prepare an official-feed evaluation cohort without model predictions or selection."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from safetrip.ingestion.advisories import CLEANING_VERSION, FEED_URL, parse_feed, US_CODE_TO_ISO3

ROOT = Path(__file__).resolve().parents[1]


def shingles(text):
    words = re.findall(r"\w+", text)
    return set(zip(words, words[1:], words[2:])) if len(words) >= 3 else {tuple(words)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".local/research/bert/fresh-source/advisories.xml")
    parser.add_argument("--dataset", type=Path, default=ROOT / ".local/research/bert/dataset-v3c")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/research/bert/fresh-holdout-v3")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Holdout exists; use a new version directory.")
    body = args.source.read_bytes()
    from safetrip.ingestion.countries import resolve_iso3
    rows = parse_feed(body)
    for index, row in enumerate(rows):
        row["iso3"] = resolve_iso3(row["country_name"], row["country_code"], allow_regions=True)
        row["source_id"] = str(index)
    code_mismatches = [{"country_name": row["country_name"], "country_code": row["country_code"],
                        "legacy_iso3": US_CODE_TO_ISO3.get(row["country_code"]), "resolved_iso3": row["iso3"]}
                       for row in rows if US_CODE_TO_ISO3.get(row["country_code"]) != row["iso3"]]
    items = ET.fromstring(body).findall("./channel/item")
    labels = {}
    for index, item in enumerate(items):
        title = item.findtext("title") or ""
        match = re.match(r"^(.+?)\s+[–-]\s+Level\s*([1-4])\b", title)
        if not match:
            raise ValueError("Official feed title lacks an unambiguous advisory label.")
        labels[str(index)] = int(match.group(2)) - 1
    historical = []
    dataset_manifest = json.loads((args.dataset / "manifest.json").read_text())
    if dataset_manifest["cleaning_version"] != CLEANING_VERSION:
        raise ValueError("Historical and fresh texts require the same cleaning version.")
    for name, expected in dataset_manifest["cleaner_source_hashes"].items():
        actual = hashlib.sha256((ROOT / "pipeline/src/safetrip/ingestion" / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Cleaner changed since historical dataset preparation.")
    for split in ("train", "validation", "test"):
        path = args.dataset / (split + ".jsonl")
        if hashlib.sha256(path.read_bytes()).hexdigest() != dataset_manifest["artifacts"][path.name]:
            raise ValueError("Historical input hash changed.")
        historical.extend(json.loads(line)["text"] for line in path.read_text().splitlines())
    previous = [shingles(text) for text in historical]
    prior_hashes = {hashlib.sha256(text.encode()).hexdigest() for text in historical}
    accepted, rejected = [], []
    fresh_hashes = {}
    for row in rows:
        text = row["description_text"]
        key = hashlib.sha256(text.encode()).hexdigest()
        features = shingles(text)
        reason = None
        if not text:
            reason = "empty_cleaned_text"
        elif key in prior_hashes:
            reason = "exact_historical_overlap"
        elif key in fresh_hashes:
            if fresh_hashes[key] != labels[row["source_id"]]:
                raise ValueError("Fresh identical text has conflicting labels; review before evaluation.")
            reason = "duplicate_fresh_text"
        elif any(min(len(features), len(old)) / max(len(features), len(old)) >= 0.85
                 and len(features & old) / len(features | old) >= 0.85 for old in previous):
            reason = "near_historical_overlap"
        if reason:
            rejected.append({"iso3": row["iso3"], "reason": reason})
        else:
            fresh_hashes[key] = labels[row["source_id"]]
            accepted.append({"text": text, "text_sha256": key, "iso3": row["iso3"],
                             "source_id": row["source_id"], "source_country_name": row["country_name"],
                             "label": labels[row["source_id"]], "group_id": row["iso3"],
                             "source_date_raw": row["pub_date_raw"]})
    # Keep similar fresh advisories together for later confidence estimation.
    parents = list(range(len(accepted)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    features = [shingles(row["text"]) for row in accepted]
    for i, left in enumerate(features):
        for j in range(i):
            right = features[j]
            if accepted[i]["iso3"] == accepted[j]["iso3"] or (min(len(left), len(right)) / max(len(left), len(right)) >= 0.85 and len(left & right) / len(left | right) >= 0.85):
                parents[root(i)] = root(j)
    for i, row in enumerate(accepted):
        row["group_id"] = accepted[root(i)]["iso3"]
    args.output.mkdir(parents=True)
    source = args.output / "holdout.jsonl"
    source.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in sorted(accepted, key=lambda row: row["iso3"])))
    report = {"source_url": FEED_URL, "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_xml_sha256": hashlib.sha256(body).hexdigest(), "cleaning_version": CLEANING_VERSION,
              "rows_in_feed": len(rows), "accepted_rows": len(accepted),
              "accepted_class_counts": dict(sorted(Counter(row["label"] + 1 for row in accepted).items())),
              "rejected": rejected, "legacy_country_mapping_mismatches": code_mismatches,
              "holdout_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "historical_manifest_sha256": hashlib.sha256((args.dataset / "manifest.json").read_bytes()).hexdigest(),
              "limitations": ["Historical country identities/dates are missing; this is not a country-disjoint holdout.",
                               "Exact/near-text filtering does not eliminate every semantic overlap.",
                               "Source publication dates vary; not every advisory is newly written.",
                               "Units are advisory documents, including separate territories and duplicate-country versions grouped together.",
                               "Models are scored only after validation-based selection is locked."]}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"rejected", "limitations", "legacy_country_mapping_mismatches"}}, indent=2))
    print("Legacy country mapping discrepancies:", len(code_mismatches))
    print("Holdout prepared; no model predictions generated.")


if __name__ == "__main__":
    main()

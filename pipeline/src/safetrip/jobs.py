"""Orchestration separated from parsing, inference, and database access."""
import csv
import json
import re
from pathlib import Path

from safetrip.config import resolve_path


def validate_advisories(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty advisory list.")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(r"[A-Z]{3}", row.get("iso3", "")):
            raise ValueError("Every advisory needs an uppercase ISO3 identifier.")
        if row["iso3"] in seen:
            raise ValueError("Duplicate ISO3 identifier in advisory input.")
        seen.add(row["iso3"])
        if not isinstance(row.get("description_text"), str) or not row["description_text"].strip():
            raise ValueError("Every advisory needs nonempty description_text.")
    return rows


def ingest(input_path=None, iso_csv=None, retain_raw=None):
    from safetrip.ingestion.advisories import fetch_feed_bytes, load_iso3_mapping, map_records
    xml = resolve_path(input_path).read_bytes() if input_path else fetch_feed_bytes()
    if retain_raw is not None:
        retain_raw(xml)  # Preserve exact bytes even if parsing subsequently fails.
    mapping = load_iso3_mapping(resolve_path(iso_csv)) if iso_csv else {}
    return validate_advisories(map_records(xml, mapping))


def incremental_score(rows, model_path, publisher, metadata):
    """Reuse only predictions whose text and inference provenance still match."""
    from hashlib import sha256
    from safetrip.inference.integrity import model_fingerprint
    validate_advisories(rows)
    metadata.update(model_version=model_fingerprint(resolve_path(model_path)),
                    inference_version="bert-cpu-max256-v1")
    cached = publisher.cached_predictions()
    changed, reused = [], []
    for row in rows:
        old = cached.get(row["iso3"])
        versions = (old.get("metadata") or {}) if old else {}
        same_text = old and isinstance(old["cleaned_text"], str) and (
            sha256(old["cleaned_text"].encode()).digest() ==
            sha256(row["description_text"].encode()).digest())
        if (same_text and old["status"] == "succeeded"
                and type(old["bert_score"]) is int and 0 <= old["bert_score"] <= 3
                and all(metadata.get(key) is not None and versions.get(key) == metadata[key]
                        for key in ("model_version", "cleaning_version", "inference_version"))):
            reused.append({key:old[key] for key in ("iso3", "cleaned_text", "bert_score", "last_run_id")})
        else:
            changed.append(row)
    predictions = score(changed, model_path) if changed else []
    metadata.update(predicted_count=len(predictions), reused_count=len(reused), advisory_count=len(rows))
    return predictions, reused


def score(rows, model_path, metadata=None):
    # Validation happens before loading the checkpoint or touching the database.
    validate_advisories(rows)
    if metadata is not None:
        from safetrip.inference.integrity import model_fingerprint
        metadata["model_version"] = model_fingerprint(resolve_path(model_path))
    from safetrip.inference.bert import load_model, score_texts
    tokenizer, model = load_model(resolve_path(model_path))
    model.to("cpu").eval()
    output = []
    for start in range(0, len(rows), 16):
        batch = rows[start:start + 16]
        predictions = score_texts([r["description_text"] for r in batch], tokenizer, model, "cpu")
        if len(predictions) != len(batch):
            raise ValueError("Model returned an unexpected prediction count.")
        for row, prediction in zip(batch, predictions):
            value = int(prediction)
            if not 0 <= value <= 3:
                raise ValueError("Model returned an invalid class ID.")
            output.append({"iso3": row["iso3"], "cleaned_text": row["description_text"], "bert_score": value})
    return output


def save_json(path, value):
    path = resolve_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Avoid overwriting the caller's prior run or a frozen fixture.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def country_rows():
    import pycountry
    return [{"iso3": c.alpha_3, "iso2": c.alpha_2, "name": c.name}
            for c in pycountry.countries if hasattr(c, "alpha_3") and hasattr(c, "alpha_2")]


def cluster_rows(path):
    rows = []
    seen = set()
    with resolve_path(path).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            iso3 = row["iso3"]
            if not re.fullmatch(r"[A-Z]{3}", iso3) or iso3 in seen:
                raise ValueError("Cluster data needs unique uppercase ISO3 identifiers.")
            seen.add(iso3)
            cluster = int(row["cluster"])
            if not 0 <= cluster <= 4:
                raise ValueError("Cluster ID outside 0..4.")
            rows.append({"iso3": iso3, "clustering_score": cluster,
                         **{key: float(row[key + "_score"]) for key in ("ppi", "gpi", "gti", "pvi")}})
    if not rows:
        raise ValueError("Empty clustering input.")
    return rows

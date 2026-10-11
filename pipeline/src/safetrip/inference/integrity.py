"""Verify mounted inference assets against a trusted, image-bundled manifest."""
import hashlib
import json
from pathlib import Path

MODEL_FILES = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
               "vocab.txt", "special_tokens_map.json")


def model_fingerprint(directory):
    """Hash the actual weights, tokenizer and configuration used by this run."""
    hashes = {}
    for name in MODEL_FILES:
        with (Path(directory) / name).open("rb") as stream:
            hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def verify_model(directory, manifest):
    directory = Path(directory)
    files = json.loads(Path(manifest).read_text())["model_files"]
    if not files:
        raise ValueError("Model manifest has no files.")
    for name, expected in files.items():
        if Path(name).name != name:
            raise ValueError("Manifest entries must be filenames.")
        path = directory / name
        if path.stat().st_size != expected["bytes"]:
            raise ValueError("Model artifact size differs from the pinned baseline.")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected["sha256"]:
            raise ValueError("Model artifact checksum differs from the pinned baseline.")

"""Verify mounted inference assets against a trusted, image-bundled manifest."""
import hashlib
import json
from pathlib import Path


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

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from safetrip.inference.integrity import verify_model


class ModelIntegrityTests(unittest.TestCase):
    def test_detects_same_size_tampering_and_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "model.safetensors"
            artifact.write_bytes(b"baseline")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"model_files": {artifact.name: {
                "bytes": 8, "sha256": hashlib.sha256(b"baseline").hexdigest()}}}))
            verify_model(root, manifest)
            artifact.write_bytes(b"modified")
            with self.assertRaises(ValueError):
                verify_model(root, manifest)
            artifact.unlink()
            with self.assertRaises(FileNotFoundError):
                verify_model(root, manifest)

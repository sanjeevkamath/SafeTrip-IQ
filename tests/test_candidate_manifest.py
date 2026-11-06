import json
from pathlib import Path
import tempfile
import unittest

from safetrip.inference.integrity import MODEL_FILES, model_fingerprint, verify_model
from research.scripts.manifest_bert_candidate import candidate_manifest


class CandidateManifestTests(unittest.TestCase):
    def test_manifest_rejects_model_changed_after_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            model = candidate / "model"
            model.mkdir()
            for name in MODEL_FILES:
                (model / name).write_bytes(name.encode())
            training = {"status": "succeeded", "test_set_used": False, "dataset_manifest_sha256": "data",
                        "cleaning_version": "v2", "label_mapping": {"1": 0}, "base_revision": "base", "best_epoch": 2}
            evaluation = {"split": "test", "dataset_manifest_sha256": "data",
                          "model_version": model_fingerprint(model), "metrics": {"macro_f1": 0.7}}
            (candidate / "training-report.json").write_text(json.dumps(training))
            (candidate / "final-test.json").write_text(json.dumps(evaluation))
            manifest = candidate_manifest(candidate)
            path = candidate / "manifest.json"
            path.write_text(json.dumps(manifest))
            verify_model(model, path)
            (model / "model.safetensors").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed since final evaluation"):
                candidate_manifest(candidate)

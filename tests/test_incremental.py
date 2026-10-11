import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from safetrip import jobs


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"iso3":"CAN", "description_text":"same text"}]
        self.metadata = {"cleaning_version":"legacy-advisory-v1"}
        self.old = {"iso3":"CAN", "cleaned_text":"same text", "bert_score":0,
                    "last_run_id":"original", "status":"succeeded", "metadata":{
                        "model_version":"fingerprint", "cleaning_version":"legacy-advisory-v1",
                        "inference_version":"bert-cpu-max256-v1"}}
        self.publisher = Mock()

    def run_scoring(self, old):
        self.publisher.cached_predictions.return_value = {"CAN":old} if old else {}
        with patch("safetrip.inference.integrity.model_fingerprint", return_value="fingerprint"), \
             patch("safetrip.jobs.score", return_value=[{"iso3":"CAN", "bert_score":1}]) as score:
            result = jobs.incremental_score(self.rows, "model", self.publisher, self.metadata)
        return result, score

    def test_unchanged_reuses_zero_class_without_loading_model(self):
        (predicted, reused), score = self.run_scoring(self.old)
        score.assert_not_called()
        self.assertEqual(predicted, [])
        self.assertEqual(reused[0]["last_run_id"], "original")
        self.assertEqual(self.metadata["reused_count"], 1)

    def test_changed_or_unverified_inputs_invalidate_cache(self):
        variants = [None]
        for key, value in (("cleaned_text","changed"), ("status","failed"),
                           ("bert_score",None), ("metadata",{})):
            row = copy.deepcopy(self.old)
            row[key] = value
            variants.append(row)
        for key in ("model_version", "cleaning_version", "inference_version"):
            row = copy.deepcopy(self.old)
            row["metadata"][key] = "older"
            variants.append(row)
        for old in variants:
            with self.subTest(old=old):
                (predicted, reused), score = self.run_scoring(old)
                score.assert_called_once()
                self.assertEqual(reused, [])
                self.assertEqual(len(predicted), 1)

    def test_raw_bytes_retained_before_parse_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.xml"
            content = b"\xef\xbb\xbf<rss>\r\nbroken"
            path.write_bytes(content)
            retain = Mock()
            with self.assertRaises(Exception):
                jobs.ingest(path, retain_raw=retain)
            retain.assert_called_once_with(content)

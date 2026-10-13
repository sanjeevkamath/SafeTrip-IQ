import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_aws_benchmark import estimated_cost, validate_definition, validate_metrics, wait_for_stop


class AwsBenchmarkRunnerTests(unittest.TestCase):
    def setUp(self):
        self.pins = {"image_digest": "a" * 64, "model_s3_key": "models/checkpoint.tar", "model_s3_version_id": "m1",
                     "model_archive_sha256": "b" * 64, "benchmark_s3_key": "benchmarks/input.json",
                     "benchmark_s3_version_id": "i1", "benchmark_sha256": "c" * 64}
        env = {"SAFETRIP_MODEL_S3_BUCKET": "bucket", "SAFETRIP_BENCHMARK_S3_BUCKET": "bucket",
               "SAFETRIP_MODEL_S3_KEY": self.pins["model_s3_key"], "SAFETRIP_MODEL_S3_VERSION_ID": "m1",
               "SAFETRIP_MODEL_S3_SHA256": self.pins["model_archive_sha256"],
               "SAFETRIP_BENCHMARK_S3_KEY": self.pins["benchmark_s3_key"], "SAFETRIP_BENCHMARK_S3_VERSION_ID": "i1",
               "SAFETRIP_BENCHMARK_SHA256": self.pins["benchmark_sha256"]}
        self.definition = {"cpu": "1024", "memory": "2048", "containerDefinitions": [{
            "name": "worker", "command": ["benchmark"], "image": "repo@sha256:" + self.pins["image_digest"],
            "environment": [{"name": name, "value": value} for name, value in env.items()],
            "logConfiguration": {"options": {"awslogs-group": "/safetrip-iq/worker"}}}]}

    def test_launch_check_rejects_database_access_or_changed_image(self):
        validate_definition(self.definition, "small", "repo", self.pins, "bucket")
        container = self.definition["containerDefinitions"][0]
        container["environment"].append({"name": "SAFETRIP_DATABASE_URL", "value": "not-a-real-secret"})
        with self.assertRaisesRegex(ValueError, "database credentials"):
            validate_definition(self.definition, "small", "repo", self.pins, "bucket")
        container["environment"].pop()
        container["image"] = "repo:latest"
        with self.assertRaisesRegex(ValueError, "pinned image"):
            validate_definition(self.definition, "small", "repo", self.pins, "bucket")

    def test_minimum_billing_duration_and_both_task_sizes(self):
        task = {"createdAt": 100, "pullStartedAt": 110, "stoppedAt": 120}
        small, large = estimated_cost(task, "small"), estimated_cost(task, "large")
        self.assertEqual(small["billed_compute_seconds"], 60)
        self.assertAlmostEqual(large["compute_usd"], small["compute_usd"] * 2, places=5)
        self.assertEqual(large["public_ipv4_usd"], small["public_ipv4_usd"])

    def test_timeout_requests_stop_for_the_same_task(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            report = {"requested_at_utc": "2000-01-01T00:00:00+00:00"}
            with patch("scripts.run_aws_benchmark.describe", return_value={"lastStatus": "RUNNING"}), patch("scripts.run_aws_benchmark.stop_task") as stop:
                with self.assertRaises(TimeoutError):
                    wait_for_stop("cluster", "task", report, path, 1)
            stop.assert_called_once_with("cluster", "task")
            self.assertTrue(json.loads(path.read_text())["stop_requested"])

    def test_failed_stop_request_marks_need_for_manual_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            report = {"requested_at_utc": "2000-01-01T00:00:00+00:00"}
            with patch("scripts.run_aws_benchmark.describe", side_effect=RuntimeError("expired session")), patch("scripts.run_aws_benchmark.stop_task", side_effect=RuntimeError("expired session")):
                with self.assertRaises(RuntimeError):
                    wait_for_stop("cluster", "task", report, Path(directory) / "report.json", 1)
            self.assertTrue(report["manual_stop_required"])

    def test_metrics_must_match_the_provenance_and_cover_every_row(self):
        inputs = {"model_version": "fingerprint", "benchmark_rows": 209}
        metrics = {"model_bootstrap": {"model_s3_version_id": "m1", "model_archive_sha256": "b" * 64},
                   "inference": {"database_access": False, "input_sha256": "c" * 64,
                                 "model_version": "fingerprint", "model_s3_version_id": "m1", "input_rows": 209,
                                 "prediction_counts": {"0": 83, "1": 80, "2": 26, "3": 20}}}
        validate_metrics(metrics, self.pins, inputs)
        metrics["inference"]["prediction_counts"]["0"] = 82
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_metrics(metrics, self.pins, inputs)

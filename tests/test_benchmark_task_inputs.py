import unittest

from scripts.prepare_benchmark_tasks import task_inputs


class BenchmarkTaskInputTests(unittest.TestCase):
    def setUp(self):
        self.outputs = {"model_bucket": {"value": "test-bucket"},
                        "ecr_repository_url": {"value": "123456789012.dkr.ecr.us-east-2.amazonaws.com/worker"}}
        self.inputs = {"complete": True, "bucket": "test-bucket", "model_s3_key": "models/hash/checkpoint.tar",
                       "model_s3_version_id": "model-version", "model_archive_sha256": "a" * 64,
                       "benchmark_s3_key": "benchmarks/input-hash.json", "benchmark_s3_version_id": "input-version",
                       "benchmark_sha256": "b" * 64}
        self.image = {"imageDetails": [{"registryId": "123456789012", "repositoryName": "worker",
                                      "imageDigest": "sha256:" + "c" * 64}]}

    def test_pins_both_versions_and_the_actual_content_addressed_keys(self):
        values = task_inputs(self.inputs, self.image, self.outputs)
        self.assertEqual(values["model_s3_key"], self.inputs["model_s3_key"])
        self.assertEqual(values["benchmark_s3_key"], self.inputs["benchmark_s3_key"])
        self.assertEqual(values["image_digest"], "c" * 64)
        self.assertTrue(values["benchmark_enabled"])

    def test_rejects_unpinned_or_cross_account_artifacts(self):
        for changes in ({"complete": False}, {"bucket": "different-bucket"}, {"model_s3_version_id": "null"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                task_inputs({**self.inputs, **changes}, self.image, self.outputs)
        self.image["imageDetails"][0]["registryId"] = "999999999999"
        with self.assertRaises(ValueError):
            task_inputs(self.inputs, self.image, self.outputs)

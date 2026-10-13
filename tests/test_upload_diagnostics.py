import subprocess
import unittest
from unittest.mock import patch

from scripts.upload_benchmark_inputs import command


class UploadDiagnosticTests(unittest.TestCase):
    def test_expired_session_identifies_the_failed_step_without_echoing_details(self):
        result = subprocess.CompletedProcess([], 1, "", "An error occurred (ExpiredToken) when calling the GetCallerIdentity operation: private-request-details")
        with patch("scripts.upload_benchmark_inputs.subprocess.run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "AWS identity lookup failed \\(ExpiredToken\\)") as raised:
                command(["aws", "sts", "get-caller-identity"])
        self.assertNotIn("private-request-details", str(raised.exception))

    def test_missing_credentials_are_distinguished_from_denied_uploads(self):
        cases = [
            ("Unable to locate credentials", "no AWS credentials"),
            ("An error occurred (AccessDenied) when calling the PutObject operation: private-request-details", "S3 upload failed \\(AccessDenied\\)"),
        ]
        for stderr, expected in cases:
            with self.subTest(stderr=stderr), patch("scripts.upload_benchmark_inputs.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", stderr)):
                with self.assertRaisesRegex(RuntimeError, expected):
                    command(["aws", "s3api", "put-object"])

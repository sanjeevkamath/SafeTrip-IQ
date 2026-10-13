import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

from safetrip.inference.s3_checkpoint import bootstrap_from_s3
from scripts.package_model import package


class FakeS3:
    def __init__(self, archive):
        self.archive = archive
        self.calls = []

    def download_file(self, bucket, key, destination, ExtraArgs):
        self.calls.append((bucket, key, ExtraArgs))
        shutil.copyfile(self.archive, destination)


class S3CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.model = self.root / "source"
        self.model.mkdir()
        files = {"config.json": b'{"test":true}', "model.safetensors": b"tiny test weights"}
        for name, data in files.items():
            (self.model / name).write_bytes(data)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"model_files": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items()}}))
        self.archive = self.root / "model.tar"
        self.report = package(self.model, self.manifest, self.archive)

    def test_pinned_version_downloads_and_verifies_before_publishing_directory(self):
        client = FakeS3(self.archive)
        destination = self.root / "downloaded"
        report = bootstrap_from_s3(bucket="private-models", key="v1/model.tar",
                                   version_id="version-123", archive_sha256=self.report["sha256"],
                                   destination=destination, manifest=self.manifest, client=client)
        self.assertEqual(client.calls, [("private-models", "v1/model.tar", {"VersionId": "version-123"})])
        self.assertEqual((destination / "model.safetensors").read_bytes(), b"tiny test weights")
        self.assertEqual(report["model_s3_version_id"], "version-123")

    def test_changed_archive_fails_before_model_directory_exists(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"tampered")
        destination = self.root / "downloaded"
        with self.assertRaisesRegex(ValueError, "archive checksum"):
            bootstrap_from_s3(bucket="private-models", key="v1/model.tar",
                              version_id="version-123", archive_sha256=self.report["sha256"],
                              destination=destination, manifest=self.manifest, client=FakeS3(self.archive))
        self.assertFalse(destination.exists())

    def test_unexpected_tar_member_is_rejected_even_with_pinned_archive_hash(self):
        bad_archive = self.root / "bad.tar"
        with tarfile.open(bad_archive, "w") as archive:
            archive.add(self.model / "config.json", arcname="../config.json")
        digest = hashlib.sha256(bad_archive.read_bytes()).hexdigest()
        destination = self.root / "downloaded"
        with self.assertRaisesRegex(ValueError, "unexpected member"):
            bootstrap_from_s3(bucket="private-models", key="v1/model.tar",
                              version_id="version-123", archive_sha256=digest,
                              destination=destination, manifest=self.manifest, client=FakeS3(bad_archive))
        self.assertFalse(destination.exists())
